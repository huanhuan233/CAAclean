from copy import deepcopy

import pytest

from app.feature_center.eaag import EaagGraph
from app.feature_center.topology import build_stable_topology


# 用途：构造包含共享边、线环和两个面的最小解析结果，覆盖 eAAG 的核心归属关系。
def _parser_result(revision: str) -> dict:
    entities = [
        {"id": f"{revision}-solid", "revision_id": revision, "entity_type": "solid",
         "source_index": None, "geometry_type": "solid", "volume": 1000.0,
         "bounding_box": {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]}},
        {"id": f"{revision}-face-plane", "revision_id": revision, "entity_type": "face",
         "geometry_type": "plane", "area": 100.0, "center": [5.0, 5.0, 0.0],
         "bounding_box": {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 0.0]},
         "geometry": {"normal": [0.0, 0.0, 1.0]}},
        {"id": f"{revision}-face-cylinder", "revision_id": revision, "entity_type": "face",
         "geometry_type": "cylinder", "area": 62.8318530718, "center": [5.0, 5.0, 5.0],
         "bounding_box": {"min": [4.0, 4.0, 0.0], "max": [6.0, 6.0, 10.0]},
         "geometry": {"radius": 1.0, "axis": [0.0, 0.0, 1.0], "center": [5.0, 5.0, 0.0]}},
        {"id": f"{revision}-edge", "revision_id": revision, "entity_type": "edge",
         "geometry_type": "circle", "length": 6.28318530718,
         "geometry": {"radius": 1.0, "center": [5.0, 5.0, 0.0], "axis": [0.0, 0.0, 1.0]}},
        {"id": f"{revision}-wire", "revision_id": revision, "entity_type": "wire",
         "geometry_type": "closed_wire", "closed": True},
    ]
    relations = [
        {"source_entity_id": f"{revision}-solid", "target_entity_id": f"{revision}-face-plane",
         "relation_type": "has_face"},
        {"source_entity_id": f"{revision}-solid", "target_entity_id": f"{revision}-face-cylinder",
         "relation_type": "has_face"},
        {"source_entity_id": f"{revision}-face-plane", "target_entity_id": f"{revision}-edge",
         "relation_type": "bounded_by_edge"},
        {"source_entity_id": f"{revision}-face-cylinder", "target_entity_id": f"{revision}-edge",
         "relation_type": "bounded_by_edge"},
        {"source_entity_id": f"{revision}-face-cylinder", "target_entity_id": f"{revision}-wire",
         "relation_type": "has_wire"},
        {"source_entity_id": f"{revision}-wire", "target_entity_id": f"{revision}-edge",
         "relation_type": "contains_edge"},
        {"source_entity_id": f"{revision}-face-plane", "target_entity_id": f"{revision}-face-cylinder",
         "relation_type": "adjacent_to"},
        {"source_entity_id": f"{revision}-face-cylinder", "target_entity_id": f"{revision}-face-plane",
         "relation_type": "adjacent_to"},
    ]
    return {
        "unit": "mm",
        "bounding_box": {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
        "entities": entities,
        "relations": relations,
        "meshes": [],
    }


# 用途：验证 Feature Center 拓扑 ID 不依赖旧解析器 revision UUID，且双跑输出稳定。
def test_stable_topology_ignores_revision_ids() -> None:
    first = build_stable_topology(_parser_result("revision-a"))
    second = build_stable_topology(_parser_result("revision-b"))

    assert first.shape_hash == second.shape_hash
    assert [item["entity_id"] for item in first.entities] == [
        item["entity_id"] for item in second.entities
    ]
    assert first.relations == second.relations


# 用途：验证 eAAG 可按解析曲面查询、追踪共享边，并保留线环包含关系。
def test_eaag_queries_surface_neighbors_shared_edges_and_wires() -> None:
    topology = build_stable_topology(_parser_result("revision-a"))
    graph = EaagGraph(topology.entities, topology.relations)
    cylinder = graph.faces_by_surface("cylinder")

    assert len(cylinder) == 1
    cylinder_id = cylinder[0]["entity_id"]
    neighbors = graph.face_neighbors(cylinder_id)
    assert len(neighbors) == 1
    assert graph.shared_edge_ids(cylinder_id, neighbors[0])
    assert graph.wire_ids(cylinder_id)
    assert graph.validate_references() == []


# 用途：验证容差来自模型尺度并保留绝对下限，不使用固定特征尺寸阈值。
def test_topology_tolerance_scales_with_bounding_box() -> None:
    small = build_stable_topology(_parser_result("small"))
    large_input = deepcopy(_parser_result("large"))
    large_input["bounding_box"] = {
        "min": [0.0, 0.0, 0.0],
        "max": [1_000_000.0, 1_000_000.0, 1_000_000.0],
    }
    large = build_stable_topology(large_input)

    assert small.tolerance_mm == 0.01
    assert large.tolerance_mm > small.tolerance_mm


# 用途：验证旧解析结果中的悬空关系会使拓扑构建失败，而不是被静默删除。
def test_stable_topology_rejects_dangling_relations() -> None:
    parser_result = _parser_result("dangling")
    parser_result["relations"].append({
        "source_entity_id": "dangling-face-plane",
        "target_entity_id": "missing-face",
        "relation_type": "adjacent_to",
    })

    with pytest.raises(ValueError, match="BREP_TOPOLOGY_RELATION_DANGLING"):
        build_stable_topology(parser_result)
