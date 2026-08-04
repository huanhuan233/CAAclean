from app.feature_center.eaag import EaagGraph
from app.feature_center.readiness import build_readiness_probes


# 用途：构造最小 eAAG 证据并验证只输出就绪度，不伪造复杂结构 Canonical Feature。
def test_readiness_probes_report_capability_without_recognition() -> None:
    entities = [
        {"entity_id": "F1", "entity_type": "face", "geometry_type": "plane", "geometry": {}},
        {"entity_id": "F2", "entity_type": "face", "geometry_type": "plane", "geometry": {}},
        {"entity_id": "F3", "entity_type": "face", "geometry_type": "bspline",
         "geometry": {"curvature_sample": {"gaussian": 0.1}}},
        {"entity_id": "W1", "entity_type": "wire", "geometry_type": "closed_wire"},
    ]
    relations = [
        {"relation_id": "R1", "relation_type": "adjacent_to",
         "source_entity_id": "F1", "target_entity_id": "F2"},
        {"relation_id": "R2", "relation_type": "has_wire",
         "source_entity_id": "F3", "target_entity_id": "W1"},
    ]
    probes = build_readiness_probes("PART1", "shape", EaagGraph(entities, relations))

    assert {probe["family"] for probe in probes} == {
        "rib_web", "cavity_island", "freeform_surface"
    }
    assert all(not probe["production_recognizer_enabled"] for probe in probes)
    assert all(not probe["canonical_feature_created"] for probe in probes)
    assert next(probe for probe in probes if probe["family"] == "freeform_surface")["status"] == (
        "verifier_prerequisites_incomplete"
    )


# 用途：验证证据不足时返回真实缺口，不把无面模型报告为可识别。
def test_readiness_probes_report_insufficient_evidence() -> None:
    probes = build_readiness_probes("PART1", "shape", EaagGraph([], []))
    assert all(probe["status"] == "insufficient_evidence" for probe in probes)
