from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import ValidationError

from app.drawing.extraction_client import VisionModelError
from app.patent_annotation.image_utils import prepare_patent_images
from app.patent_annotation.errors import PatentAnnotationError
from app.patent_annotation.schemas import (
    LocalizationCandidate,
    ModelLocalizationBox,
    ModelLocalizationItem,
    ModelLocalizationOutput,
    NormalizedBox,
    NormalizedLocalizationItem,
    NormalizedLocalizationResult,
    NormalizedPoint,
)


PATENT_LOCALIZATION_RULES = """You are localizing visible patent drawing reference numbers.
Rules:
1. Only return refs from the provided candidate JSON.
2. A part is visible only when the drawing contains that referenced physical part.
3. Do not infer hidden, implied, cross-section-only, or text-only parts.
4. Coordinates use the supplied 0-1000 grid image, not pixels.
5. Anchor is the best point on the visible part, preferably near the reference leader or label.
6. Bbox is optional and should tightly enclose the visible part when confident.
7. If unsure, set visible=false or confidence below 0.5 with a short reason.
8. Return strict JSON matching the schema: {"items":[...]}.
9. Do not add explanations outside JSON and do not invent refs, names, figures, or values.
"""


class PatentLocalizationService:
    def __init__(self, vision_client, model_name: str | None = None, *, batch_size: int = 16):
        self.vision_client = vision_client
        self.model_name = model_name or getattr(vision_client, "model", "")
        self.batch_size = batch_size

    async def localize(
        self,
        image_path: Path,
        *,
        figure_no: str,
        figure_description: str,
        figure_context: str,
        candidates: list[LocalizationCandidate],
        work_dir: Path,
    ) -> NormalizedLocalizationResult:
        assets = prepare_patent_images(image_path, work_dir)
        merged: dict[str, NormalizedLocalizationItem] = {}
        warnings: list[str] = []
        for batch in _chunks(candidates, self.batch_size):
            batch_refs = {candidate.ref_no for candidate in batch}
            prompt = build_patent_localization_prompt(
                figure_no=figure_no,
                figure_description=figure_description,
                figure_context=figure_context,
                candidates=batch,
                model_name=self.model_name,
            )
            try:
                payload = await self.vision_client.complete_json(
                    task_name="patent_page_localization",
                    schema=ModelLocalizationOutput,
                    messages=[{"type": "text", "text": prompt}],
                    image_paths=[assets.clean_path, assets.grid_path],
                )
            except VisionModelError as exc:
                raise PatentAnnotationError("patent_localization_failed", exc.message) from exc
            for item in _valid_model_items(payload, warnings):
                if item.ref_no not in batch_refs:
                    warnings.append(f"unknown_ref_{item.ref_no}")
                    continue
                normalized, item_warnings = _normalize_item(item)
                warnings.extend(item_warnings)
                previous = merged.get(item.ref_no)
                if previous is None or normalized.confidence > previous.confidence:
                    merged[item.ref_no] = normalized

        ordered = [merged[ref_no] for ref_no in [candidate.ref_no for candidate in candidates] if ref_no in merged]
        return NormalizedLocalizationResult(items=ordered, warnings=_dedupe(warnings))


def build_patent_localization_prompt(
    *,
    figure_no: str,
    figure_description: str,
    figure_context: str,
    candidates: list[LocalizationCandidate],
    model_name: str | None = None,
) -> str:
    candidate_payload = [{"ref_no": candidate.ref_no, "name": candidate.name} for candidate in candidates]
    context = figure_context[:2000]
    return "\n".join(
        [
            PATENT_LOCALIZATION_RULES,
            f"Model: {model_name or 'vision'}",
            f"Figure number: {figure_no}",
            f"Figure description: {figure_description}",
            f"Figure context: {context}",
            "Candidates JSON:",
            json.dumps(candidate_payload, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def _chunks(items: list[LocalizationCandidate], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _valid_model_items(payload, warnings: list[str]) -> list[ModelLocalizationItem]:
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        warnings.append("invalid_model_output")
        return []
    items: list[ModelLocalizationItem] = []
    for index, raw_item in enumerate(raw_items):
        try:
            items.append(ModelLocalizationItem.model_validate(raw_item))
        except ValidationError:
            ref = raw_item.get("ref_no") if isinstance(raw_item, dict) else index
            warnings.append(f"invalid_model_item_{ref}")
    return items


def _normalize_item(item) -> tuple[NormalizedLocalizationItem, list[str]]:
    warnings: list[str] = []
    if _has_non_finite_coordinates(item):
        warnings.append(f"non_finite_coordinate_{item.ref_no}")
    anchor = _normalize_point(item.anchor) if item.anchor else None
    bbox = _normalize_box(item.bbox) if item.bbox else None
    visible = item.visible

    if visible and anchor is None:
        visible = False
        warnings.append(f"visible_without_anchor_{item.ref_no}")

    review_state = _review_state(visible, item.confidence)
    if visible and anchor and bbox and not _point_inside_bbox(anchor, bbox):
        if review_state != "rejected":
            review_state = "review"
        warnings.append(f"anchor_outside_bbox_{item.ref_no}")

    return (
        NormalizedLocalizationItem(
            ref_no=item.ref_no,
            visible=visible,
            confidence=item.confidence,
            reason=item.reason[:120],
            anchor=anchor if visible else None,
            bbox=bbox if visible else None,
            review_state=review_state,
        ),
        warnings,
    )


def _review_state(visible: bool, confidence: float) -> str:
    if not visible or confidence < 0.45:
        return "rejected"
    if confidence >= 0.72:
        return "accepted"
    return "review"


def _normalize_point(point) -> NormalizedPoint:
    return NormalizedPoint(x=_clamp(point.x / 1000), y=_clamp(point.y / 1000))


def _normalize_box(box: ModelLocalizationBox | None) -> NormalizedBox | None:
    if box is None:
        return None
    x_min, x_max = sorted((_clamp(box.x_min / 1000), _clamp(box.x_max / 1000)))
    y_min, y_max = sorted((_clamp(box.y_min / 1000), _clamp(box.y_max / 1000)))
    return NormalizedBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _point_inside_bbox(point: NormalizedPoint, bbox: NormalizedBox) -> bool:
    return bbox.x_min <= point.x <= bbox.x_max and bbox.y_min <= point.y <= bbox.y_max


def _has_non_finite_coordinates(item: ModelLocalizationItem) -> bool:
    values: list[float] = []
    if item.anchor:
        values.extend([item.anchor.x, item.anchor.y])
    if item.bbox:
        values.extend([item.bbox.x_min, item.bbox.y_min, item.bbox.x_max, item.bbox.y_max])
    return any(not math.isfinite(value) for value in values)


def _clamp(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
