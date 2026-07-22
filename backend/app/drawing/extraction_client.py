from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from openai import APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel, ValidationError


class VisionModelError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def parse_model_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError as exc:
                raise VisionModelError("vision_invalid_json", "model returned invalid JSON") from exc
        raise VisionModelError("vision_invalid_json", "model returned non-JSON content")


class VisionJsonClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int,
        max_retries: int,
        extra_body: dict | None = None,
    ):
        self.model = model
        self.max_retries = max_retries
        self.extra_body = extra_body or {}
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

    async def health_check(self):
        try:
            await self.client.models.list()
        except Exception as exc:
            raise VisionModelError("vision_health_check_failed", "vision health check failed") from exc

    async def complete_json(self, *, task_name: str, schema: type[BaseModel], messages: list[dict], image_paths: list[Path]) -> dict:
        content = [*messages]
        for image_path in image_paths:
            content.append({"type": "image_url", "image_url": {"url": _image_data_url(image_path)}})
        user_message = {"role": "user", "content": content}
        system = {
            "role": "system",
            "content": (
                "Only output JSON. Do not output Markdown. Do not infer invisible values. "
                "Return null or needs_review for ambiguous content. Do not generate YAML. Do not judge STEP compliance."
            ),
        }
        last_error: Exception | None = None
        use_response_format = True
        for _attempt in range(self.max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
                    "messages": [system, user_message],
                    "temperature": 0,
                    "extra_body": self.extra_body,
                }
                if use_response_format:
                    kwargs["response_format"] = {"type": "json_object"}
                response = await self.client.chat.completions.create(**kwargs)
                text = response.choices[0].message.content or ""
                payload = _coerce_schema_payload(parse_model_json(text), schema)
                return payload
            except APIStatusError as exc:
                message = str(exc).lower()
                if "response_format" in message and use_response_format:
                    use_response_format = False
                    continue
                if exc.status_code in {400, 415} and "image" in message:
                    raise VisionModelError("vision_model_not_multimodal", "vision model does not accept image_url content") from exc
                if exc.status_code not in {429, 500, 502, 503, 504}:
                    raise VisionModelError("vision_request_failed", "vision request failed") from exc
                last_error = exc
            except APITimeoutError as exc:
                last_error = exc
            except (VisionModelError, ValidationError) as exc:
                last_error = exc
        raise VisionModelError("vision_request_failed", f"vision task failed: {last_error.__class__.__name__ if last_error else 'unknown'}")


def _image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/png"
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    if suffix == ".webp":
        mime = "image/webp"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _coerce_schema_payload(payload: dict, schema: type[BaseModel]) -> dict:
    try:
        schema.model_validate(payload)
        return payload
    except ValidationError:
        pass
    candidate_keys = {
        "ProductInfoResult": ["product_info", "product", "result"],
        "TableExtractionResult": ["table", "table_result", "result"],
        "SymbolDefinitionResult": ["symbols_result", "symbol_result", "result"],
        "TargetRowResult": ["target_row", "target", "result"],
    }.get(schema.__name__, ["result"])
    for key in candidate_keys:
        candidate = payload.get(key)
        if isinstance(candidate, dict):
            return candidate
        if schema.__name__ == "SymbolDefinitionResult" and isinstance(candidate, list):
            wrapped = {"symbols": candidate}
            return wrapped
    if len(payload) == 1:
        only_value = next(iter(payload.values()))
        if isinstance(only_value, dict):
            return only_value
    return payload
