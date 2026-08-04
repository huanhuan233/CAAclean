import math

from app.feature_center.visual_review import (
    build_visual_cache_key,
    route_visual_review,
    validate_offline_visual_response,
)


# 用途：验证确定性 Hole 不需要视觉，stale 状态只进入人工审查且不会远程调用。
def test_visual_router_keeps_remote_calls_disabled() -> None:
    verified = route_visual_review("shape", "F1", "verified", ["FACE1"])
    stale = route_visual_review("shape", "F1", "verified", ["FACE1"], stale=True)

    assert verified.decision == "not_needed"
    assert stale.decision == "human_review_only"
    assert verified.visual_call_count == stale.visual_call_count == 0


# 用途：验证缺少真实面时明确阻塞，不允许只凭视觉产生几何定位。
def test_visual_router_blocks_missing_geometry_evidence() -> None:
    decision = route_visual_review("shape", "F2", "ambiguous", [])
    assert decision.decision == "blocked_by_missing_evidence"


# 用途：验证缓存键不受候选面输入顺序影响，但受提示词和模型版本约束。
def test_visual_cache_key_is_deterministic() -> None:
    first = build_visual_cache_key("s", ["B", "A"], "e1", "p1", "m1")
    second = build_visual_cache_key("s", ["A", "B"], "e1", "p1", "m1")
    changed = build_visual_cache_key("s", ["A", "B"], "e1", "p2", "m1")
    assert first == second
    assert first != changed


# 用途：验证越界坐标和非有限置信度被拒绝，不能进入 Face-ID 回链。
def test_visual_response_rejects_invalid_coordinates_and_nonfinite_values() -> None:
    response = {
        "analysis_version": "1.0",
        "candidates": [{
            "classification_confidence": math.nan,
            "localization_confidence": 0.5,
            "regions": [{
                "view_id": "iso_001",
                "normalized_polygon": [[0.0, 0.0], [1.1, 0.2], [0.4, 0.5]],
            }],
        }],
    }
    errors = validate_offline_visual_response(response)
    assert any("NONFINITE" in error for error in errors)
    assert any("COORDINATE_INVALID" in error for error in errors)
