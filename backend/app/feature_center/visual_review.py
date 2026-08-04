"""视觉审查路由和离线交换协议；本模块不会发起远程调用。"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from .contracts import stable_id


VISUAL_REVIEW_PROTOCOL_VERSION = "visual_review_v1"
VISUAL_PROMPT_VERSION = "feature_center_review_prompt_v1"


@dataclass(frozen=True)
class VisualReviewDecision:
    """保存确定性审查路由结论，不把视觉建议混入权威测量。"""

    review_request_id: str
    decision: str
    reason: str
    cache_key: str
    visual_call_count: int = 0


# 用途：用几何、证据配置、提示词和模型版本生成可复现缓存键。
def build_visual_cache_key(
    shape_hash: str,
    candidate_face_ids: list[str],
    evidence_config_version: str,
    prompt_version: str,
    model_version: str,
) -> str:
    payload = {
        "candidate_face_ids": sorted(set(candidate_face_ids)),
        "evidence_config_version": evidence_config_version,
        "model_version": model_version,
        "prompt_version": prompt_version,
        "shape_hash": shape_hash,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# 用途：在禁用远程视觉的产品策略下，根据融合状态生成离线审查路由。
def route_visual_review(
    shape_hash: str,
    feature_id: str,
    verification_status: str,
    face_ids: list[str],
    stale: bool = False,
) -> VisualReviewDecision:
    cache_key = build_visual_cache_key(
        shape_hash, face_ids, "analysis_render_v1", VISUAL_PROMPT_VERSION, "disabled"
    )
    request_id = stable_id("VR", shape_hash, feature_id, cache_key)
    if not face_ids:
        return VisualReviewDecision(
            request_id, "blocked_by_missing_evidence", "缺少可回链的真实 Face", cache_key
        )
    if stale:
        return VisualReviewDecision(
            request_id, "human_review_only", "原生设计状态陈旧，必须保留语义与导出几何冲突", cache_key
        )
    if verification_status == "verified":
        return VisualReviewDecision(
            request_id, "not_needed", "B-Rep 规则已完成确定性验证", cache_key
        )
    return VisualReviewDecision(
        request_id, "disabled_by_policy", "当前阶段禁用远程视觉调用", cache_key
    )


# 用途：严格校验离线视觉响应的归一化坐标和有限置信度，拒绝污染后续融合。
def validate_offline_visual_response(response: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if response.get("analysis_version") != "1.0":
        errors.append("VISUAL_SCHEMA_VERSION_INVALID")
    candidates = response.get("candidates")
    if not isinstance(candidates, list):
        return errors + ["VISUAL_CANDIDATES_INVALID"]
    for candidate_index, candidate in enumerate(candidates):
        for field_name in ("classification_confidence", "localization_confidence"):
            value = candidate.get(field_name)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                errors.append(f"VISUAL_CONFIDENCE_NONFINITE:{candidate_index}:{field_name}")
            elif not 0.0 <= float(value) <= 1.0:
                errors.append(f"VISUAL_CONFIDENCE_OUT_OF_RANGE:{candidate_index}:{field_name}")
        for region_index, region in enumerate(candidate.get("regions", [])):
            polygon = region.get("normalized_polygon")
            if not isinstance(polygon, list) or len(polygon) < 3:
                errors.append(f"VISUAL_POLYGON_INVALID:{candidate_index}:{region_index}")
                continue
            for point_index, point in enumerate(polygon):
                if not isinstance(point, list) or len(point) != 2:
                    errors.append(
                        f"VISUAL_POINT_INVALID:{candidate_index}:{region_index}:{point_index}"
                    )
                    continue
                if any(
                    not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or not 0.0 <= float(value) <= 1.0
                    for value in point
                ):
                    errors.append(
                        f"VISUAL_COORDINATE_INVALID:{candidate_index}:{region_index}:{point_index}"
                    )
    return sorted(set(errors))
