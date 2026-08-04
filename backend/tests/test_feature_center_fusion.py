from app.feature_center.eaag import EaagGraph
from app.feature_center.fusion import fuse_native_holes


# 用途：构造已建立稳定 ID 的简单盲孔 eAAG，用于验证多源记录和引用守恒。
def _graph() -> EaagGraph:
    entities = [
        {"entity_id": "FACE-A", "entity_type": "face", "geometry_type": "cylinder",
         "geometry": {"radius": 5.0, "axis": [0, 0, 1], "center": [0, 0, 0]},
         "bounding_box": {"min": [-5, -5, 0], "max": [5, 5, 12]}, "center": [0, 0, 6]},
        {"entity_id": "FACE-B", "entity_type": "face", "geometry_type": "cylinder",
         "geometry": {"radius": 5.0, "axis": [0, 0, 1], "center": [0, 0, 0]},
         "bounding_box": {"min": [-5, -5, 0], "max": [5, 5, 12]}, "center": [0, 0, 6]},
        {"entity_id": "FACE-C", "entity_type": "face", "geometry_type": "plane",
         "geometry": {"normal": [0, 0, 1]},
         "bounding_box": {"min": [-5, -5, 12], "max": [5, 5, 12]}, "center": [0, 0, 12]},
    ]
    relations = [
        {"relation_id": "R1", "relation_type": "adjacent_to",
         "source_entity_id": "FACE-A", "target_entity_id": "FACE-B"},
        {"relation_id": "R2", "relation_type": "adjacent_to",
         "source_entity_id": "FACE-A", "target_entity_id": "FACE-C"},
        {"relation_id": "R3", "relation_type": "adjacent_to",
         "source_entity_id": "FACE-B", "target_entity_id": "FACE-C"},
    ]
    return EaagGraph(entities, relations)


# 用途：构造一个原生 Hole 和 Pocket 反例，确保融合只消费专用 Decoder 的事实。
def _native_features(update_status="up_to_date") -> list[dict]:
    return [
        {
            "feature_id": "F000001", "decoder_id": "NativeHoleDecoder",
            "display_name": "Hole.5", "update_status": update_status,
            "native_hole": {
                "automation_alias": "CoolingPort_A", "hole_type": "simple",
                "diameter_mm": 10.0, "origin_mm": [0, 0, 0], "direction": [0, 0, 1],
                "bottom_limit": {"mode": "offset", "depth_mm": 12.0},
                "head": {"kind": "none", "diameter_mm": None, "depth_mm": None},
                "thread": {"enabled": False},
            },
        },
        {"feature_id": "F000002", "decoder_id": "generic", "startup_type": "Pocket"},
    ]


# 用途：验证 Native 与 B-Rep Observation 分离、Canonical 引用完整且测量只来自 B-Rep。
def test_fusion_creates_two_observations_one_canonical_and_brep_measurements() -> None:
    result = fuse_native_holes("PART1", _graph(), _native_features(), 0.01, "shape-hash")

    assert len(result.observations) == 2
    assert len(result.canonical_features) == 1
    canonical = result.canonical_features[0]
    assert canonical.native_feature_ids == ["F000001"]
    assert canonical.geometry_refs.face_ids == ["FACE-A", "FACE-B", "FACE-C"]
    assert canonical.review_state == "auto_verified"
    assert all(measurement.source == "brep_deterministic" for measurement in result.measurements)
    assert {measurement.name for measurement in result.measurements} == {"diameter", "depth"}
    assert len(result.feature_geometry_links) == 3


# 用途：验证 stale 语义不会被当前 STEP 几何覆盖，融合结果必须进入复核并保留冲突状态。
def test_stale_native_semantic_forces_review_without_discarding_geometry() -> None:
    result = fuse_native_holes(
        "PART1", _graph(), _native_features("not_up_to_date"), 0.01, "shape-hash"
    )

    canonical = result.canonical_features[0]
    assert canonical.review_state == "needs_review"
    assert canonical.provenance["native_update_status"] == "not_up_to_date"
    assert canonical.provenance["design_geometry_agreement"] == "stale_requires_review"
