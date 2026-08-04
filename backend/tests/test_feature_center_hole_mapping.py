from app.feature_center.eaag import EaagGraph
from app.feature_center.hole_mapping import HoleGeometryVerifier


# 用途：构造稳定 Face 节点，直接测试参数引导逻辑而不依赖 CATIA 或 FreeCAD 进程。
def _face(face_id, surface, geometry, bounds, area=10.0):
    return {
        "entity_id": face_id,
        "entity_type": "face",
        "geometry_type": surface,
        "geometry": geometry,
        "bounding_box": bounds,
        "area": area,
        "center": [
            (bounds["min"][axis] + bounds["max"][axis]) * 0.5 for axis in range(3)
        ],
    }


# 用途：构造两片接缝圆柱壁和可选底面，模拟 CATIA STEP 导出的真实分面方式。
def _hole_graph(radius=5.0, depth=12.0, include_bottom=True, include_through_openings=False):
    bounds = {"min": [-radius, -radius, 0.0], "max": [radius, radius, depth]}
    entities = [
        _face("FACE-WALL-A", "cylinder", {"radius": radius, "axis": [0, 0, 1],
              "center": [0, 0, 0]}, bounds),
        _face("FACE-WALL-B", "cylinder", {"radius": radius, "axis": [0, 0, 1],
              "center": [0, 0, 0]}, bounds),
    ]
    relations = [
        {"relation_id": "R1", "relation_type": "adjacent_to",
         "source_entity_id": "FACE-WALL-A", "target_entity_id": "FACE-WALL-B"},
    ]
    if include_bottom:
        bottom_bounds = {"min": [-radius, -radius, depth], "max": [radius, radius, depth]}
        entities.append(_face("FACE-BOTTOM", "plane", {"normal": [0, 0, 1]}, bottom_bounds))
        for index, wall in enumerate(("FACE-WALL-A", "FACE-WALL-B"), 2):
            relations.append({"relation_id": f"R{index}", "relation_type": "adjacent_to",
                              "source_entity_id": wall, "target_entity_id": "FACE-BOTTOM"})
    if include_through_openings:
        for side, coordinate in (("TOP", 0.0), ("EXIT", depth)):
            plane_id = f"FACE-{side}"
            plane_bounds = {"min": [-radius * 2, -radius * 2, coordinate],
                            "max": [radius * 2, radius * 2, coordinate]}
            entities.append(_face(plane_id, "plane", {"normal": [0, 0, 1]}, plane_bounds,
                                  area=(radius * 4) ** 2))
            relations.append({"relation_id": f"R-{side}", "relation_type": "adjacent_to",
                              "source_entity_id": "FACE-WALL-A", "target_entity_id": plane_id})
    return EaagGraph(entities, relations)


# 用途：构造与 CAA features.jsonl 同形的原生 Hole 记录。
def _native_hole(alias="CoolingPort_A", limit="offset", depth=12.0):
    return {
        "feature_id": "F000001",
        "decoder_id": "NativeHoleDecoder",
        "display_name": "Hole.5",
        "update_status": "up_to_date",
        "native_hole": {
            "automation_alias": alias,
            "diameter_mm": 10.0,
            "origin_mm": [0.0, 0.0, 0.0],
            "direction": [0.0, 0.0, 1.0],
            "hole_type": "simple",
            "bottom_limit": {"mode": limit, "depth_mm": depth if limit == "offset" else None},
            "head": {"kind": "none", "diameter_mm": None, "depth_mm": None},
            "thread": {"enabled": False},
        },
    }


# 用途：验证不含 Hole 语义的别名仍通过专用参数匹配两片孔壁和真实底面。
def test_blind_hole_mapping_is_name_independent_and_keeps_face_roles() -> None:
    result = HoleGeometryVerifier(0.01).verify(_native_hole(), _hole_graph())

    assert result.status == "verified"
    assert result.body_wall_face_ids == ["FACE-WALL-A", "FACE-WALL-B"]
    assert result.bottom_face_ids == ["FACE-BOTTOM"]
    assert result.match_method == "native_hole_parameter_guided_eaag"
    assert result.parameter_residuals["radius_mm"] == 0.0


# 用途：验证 Up To Last 只定位贯穿壁，不伪造不存在的底面和深度。
def test_up_to_last_hole_does_not_invent_bottom_face() -> None:
    result = HoleGeometryVerifier(0.01).verify(
        _native_hole(limit="up_to_last", depth=None),
        _hole_graph(depth=25.0, include_bottom=False, include_through_openings=True),
    )

    assert result.status == "verified"
    assert result.bottom_face_ids == []
    assert result.parameter_residuals["depth_mm"] is None


# 用途：验证只有同轴圆柱但缺少双开口上下文时不能把 Up To Last 自动判为贯穿孔。
def test_up_to_last_requires_two_opening_context_faces() -> None:
    result = HoleGeometryVerifier(0.01).verify(
        _native_hole(limit="up_to_last", depth=None),
        _hole_graph(depth=25.0, include_bottom=False),
    )

    assert result.status == "needs_review"
    assert "through_opening_context" in result.unmatched_expected_geometry


# 用途：验证非 NativeHoleDecoder 对象即使几何看似圆孔也会被拒绝，防止 Pocket 误判。
def test_non_native_feature_is_rejected_before_geometry_matching() -> None:
    pocket = _native_hole()
    pocket["decoder_id"] = "generic"
    pocket["startup_type"] = "Pocket"

    result = HoleGeometryVerifier(0.01).verify(pocket, _hole_graph())

    assert result.status == "rejected"
    assert result.matched_face_ids == []
