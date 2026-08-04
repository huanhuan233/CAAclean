import json

import pytest

from app.feature_center.mesh import build_lightweight_mesh
from app.feature_center.topology import StableTopology


# 用途：构造两个 Face 的旧解析网格及稳定编号映射，测试不依赖 FreeCAD 运行时。
def _inputs():
    parser_result = {
        "meshes": [
            {"entity_id": "legacy-b", "positions": [[0, 0, 1], [1, 0, 1], [0, 1, 1]],
             "indices": [[0, 1, 2]], "triangle_count": 1},
            {"entity_id": "legacy-a", "positions": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
             "indices": [[0, 1, 2]], "triangle_count": 1},
        ]
    }
    topology = StableTopology(
        shape_hash="shape-hash", tolerance_mm=0.01,
        entities=[
            {"entity_id": "FACE-A", "entity_type": "face"},
            {"entity_id": "FACE-B", "entity_type": "face"},
        ],
        relations=[],
        source_entity_map={"legacy-a": "FACE-A", "legacy-b": "FACE-B"},
    )
    links = [
        {"link_id": "L1", "feature_center_id": "FC1", "face_id": "FACE-A", "role": "wall"},
        {"link_id": "L2", "feature_center_id": "FC1", "face_id": "FACE-B", "role": "bottom"},
    ]
    return parser_result, topology, links


# 用途：验证 GLB、Face→Primitive、Feature→Primitive 与 Primitive→Face 映射完整且双跑稳定。
def test_lightweight_mesh_is_deterministic_and_bidirectional() -> None:
    first = build_lightweight_mesh(*_inputs())
    second = build_lightweight_mesh(*_inputs())

    assert first.model_glb[:4] == b"glTF"
    assert first.model_glb == second.model_glb
    assert first.face_mesh_map == second.face_mesh_map
    assert set(first.face_mesh_map["faces"]) == {"FACE-A", "FACE-B"}
    assert first.feature_mesh_map["features"]["FC1"]["face_ids"] == ["FACE-A", "FACE-B"]
    for primitive_id, face_id in first.face_mesh_map["primitive_to_face"].items():
        assert first.face_mesh_map["faces"][face_id]["mesh_primitive_id"] == primitive_id
    assert first.triangle_count == 2


# 用途：验证越界三角形不会生成错误映射或看似可用的 GLB。
def test_lightweight_mesh_rejects_invalid_triangle_indices() -> None:
    parser_result, topology, links = _inputs()
    parser_result["meshes"][0]["indices"] = [[0, 1, 99]]

    with pytest.raises(ValueError, match="MESH_INDEX_OUT_OF_RANGE"):
        build_lightweight_mesh(parser_result, topology, links)


# 用途：验证映射对象可以用严格 JSON 编码，且索引和计数保持 JSON number。
def test_lightweight_maps_are_json_serializable() -> None:
    result = build_lightweight_mesh(*_inputs())
    encoded = json.dumps(result.face_mesh_map, allow_nan=False)

    assert '"triangle_count": 1' in encoded


# 用途：验证空网格被跳过后，映射索引仍指向 GLB 中真实连续的 Primitive。
def test_empty_mesh_does_not_shift_primitive_indices() -> None:
    parser_result, topology, links = _inputs()
    parser_result["meshes"].insert(0, {
        "entity_id": "legacy-a", "positions": [], "indices": [], "triangle_count": 0,
    })

    result = build_lightweight_mesh(parser_result, topology, links)

    indices = sorted(item["primitive_index"] for item in result.face_mesh_map["faces"].values())
    assert indices == [0, 1]
