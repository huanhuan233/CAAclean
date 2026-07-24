from __future__ import annotations

import asyncio
import io
import json
import shlex
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx


class MineruError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class MineruClient:
    def __init__(
        self,
        *,
        mode: str = "disabled",
        url: str | None = None,
        command: str | None = None,
        timeout: int = 180,
        transport: Callable[[Path], Awaitable[dict]] | None = None,
    ):
        self.mode = mode
        self.url = url
        self.command = command
        self.timeout = timeout
        self.transport = transport

    async def fetch_payload(self, input_path: Path) -> dict:
        if self.mode == "disabled":
            raise MineruError("mineru_not_configured", "MinerU provider is disabled")
        try:
            if self.transport:
                payload = await asyncio.wait_for(self.transport(input_path), timeout=self.timeout)
            elif self.mode == "http":
                payload = await asyncio.wait_for(asyncio.to_thread(self._http_fetch, input_path), timeout=self.timeout)
            elif self.mode == "command":
                payload = await asyncio.wait_for(self._command_fetch(input_path), timeout=self.timeout)
            else:
                raise MineruError("mineru_not_configured", "unsupported MinerU layout mode")
        except TimeoutError as exc:
            raise MineruError("mineru_timeout", "MinerU layout detection timed out") from exc
        except MineruError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MineruError("mineru_invalid_result", "MinerU returned an invalid JSON result") from exc
        except Exception as exc:
            raise MineruError("mineru_connection_failed", "MinerU layout detection failed") from exc
        if not isinstance(payload, dict):
            raise MineruError("mineru_invalid_result", "MinerU returned an invalid JSON result")
        return payload

    def _http_fetch(self, input_path: Path) -> dict:
        if not self.url:
            raise MineruError("mineru_not_configured", "MINERU_LAYOUT_URL is not configured")
        request = urllib.request.Request(
            self.url,
            data=input_path.read_bytes(),
            method="POST",
            headers={"Content-Type": "application/octet-stream"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    async def _command_fetch(self, input_path: Path) -> dict:
        if not self.command:
            raise MineruError("mineru_not_configured", "MINERU_LAYOUT_COMMAND is not configured")
        args = [*shlex.split(self.command), str(input_path)]
        process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, _stderr = await process.communicate()
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(process.wait(), timeout=1)
            except TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            raise
        if process.returncode != 0:
            raise MineruError("mineru_connection_failed", "MinerU command failed")
        return json.loads(stdout.decode("utf-8"))


class MineruDocumentClient:
    """Client for the MinerU 3.x synchronous document parsing API."""

    MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024

    def __init__(
        self,
        *,
        api_url: str,
        endpoint: str = "file_parse",
        backend: str = "hybrid-auto-engine",
        ocr_lang: str = "ch",
        result_mode: str = "zip",
        enable_table: bool = True,
        enable_formula: bool = True,
        enable_image_analysis: bool = True,
        enable_ocr: bool = True,
        server_url: str | None = None,
        timeout: int = 3600,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.endpoint_url = f"{api_url.rstrip('/')}/{endpoint.strip('/')}"
        self.backend = backend
        self.ocr_lang = ocr_lang
        self.result_mode = result_mode
        self.enable_table = enable_table
        self.enable_formula = enable_formula
        self.enable_image_analysis = enable_image_analysis
        self.enable_ocr = enable_ocr
        self.server_url = server_url
        self.timeout = timeout
        self.transport = transport

    async def fetch_payload(self, input_path: Path) -> dict:
        if not self.endpoint_url.startswith(("http://", "https://")):
            raise MineruError("mineru_not_configured", "MINERU_API_URL is not configured")

        form = {
            "lang_list": self.ocr_lang,
            "backend": self.backend,
            "parse_method": "auto" if self.enable_ocr else "txt",
            "formula_enable": _bool_text(self.enable_formula),
            "table_enable": _bool_text(self.enable_table),
            "image_analysis": _bool_text(self.enable_image_analysis),
            "return_md": "true",
            "return_middle_json": "false",
            "return_model_output": "false",
            "return_content_list": "true",
            "return_images": "false",
            "response_format_zip": _bool_text(self.result_mode.lower() == "zip"),
            "return_original_file": "false",
        }
        if self.server_url:
            form["server_url"] = self.server_url

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                transport=self.transport,
            ) as client:
                with input_path.open("rb") as pdf_file:
                    response = await client.post(
                        self.endpoint_url,
                        data=form,
                        files={"files": (input_path.name, pdf_file, "application/pdf")},
                    )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise MineruError("mineru_timeout", "MinerU document parsing timed out") from exc
        except (httpx.HTTPError, OSError) as exc:
            raise MineruError("mineru_connection_failed", "MinerU document parsing failed") from exc

        try:
            content_type = response.headers.get("content-type", "").lower()
            if "zip" in content_type or response.content.startswith(b"PK"):
                return self._read_zip_payload(response.content)
            return self._normalize_json_payload(response.json())
        except MineruError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile, ValueError) as exc:
            raise MineruError("mineru_invalid_result", "MinerU returned an invalid document result") from exc

    @classmethod
    def _read_zip_payload(cls, content: bytes) -> dict:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if sum(info.file_size for info in infos) > cls.MAX_UNCOMPRESSED_BYTES:
                raise MineruError("mineru_invalid_result", "MinerU result archive is too large")

            markdown_parts: list[str] = []
            content_items: list[dict[str, Any]] = []
            for info in sorted(infos, key=lambda item: item.filename):
                lower_name = info.filename.lower()
                if lower_name.endswith(".md"):
                    markdown_parts.append(archive.read(info).decode("utf-8"))
                elif lower_name.endswith("content_list.json"):
                    parsed = json.loads(archive.read(info).decode("utf-8"))
                    if isinstance(parsed, list):
                        content_items.extend(item for item in parsed if isinstance(item, dict))
                    elif isinstance(parsed, dict) and isinstance(parsed.get("content_list"), list):
                        content_items.extend(item for item in parsed["content_list"] if isinstance(item, dict))

        payload: dict[str, Any] = {}
        if markdown_parts:
            payload["markdown"] = "\n\n".join(part.strip() for part in markdown_parts if part.strip())
        if content_items:
            payload["content_list"] = content_items
        if not payload:
            raise MineruError("mineru_invalid_result", "MinerU result archive contains no text output")
        return payload

    @staticmethod
    def _normalize_json_payload(payload: Any) -> dict:
        if not isinstance(payload, dict):
            raise MineruError("mineru_invalid_result", "MinerU returned an invalid JSON result")
        results = payload.get("results")
        if not isinstance(results, dict):
            return payload

        for result in results.values():
            if not isinstance(result, dict):
                continue
            normalized: dict[str, Any] = {}
            markdown = result.get("md_content") or result.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                normalized["markdown"] = markdown
            content_list = result.get("content_list")
            if isinstance(content_list, str):
                content_list = json.loads(content_list)
            if isinstance(content_list, list):
                normalized["content_list"] = content_list
            if normalized:
                return normalized
        raise MineruError("mineru_invalid_result", "MinerU JSON result contains no text output")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
