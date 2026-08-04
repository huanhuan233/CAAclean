"""Face 级轻量化 GLB 与双向映射生成。"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from typing import Any

from .contracts import stable_id
from .topology import StableTopology


@dataclass(frozen=True)
class LightweightMeshResult:
    """保存 GLB 字节、映射表和几何规模统计。"""

    model_glb: bytes
    face_mesh_map: dict[str, Any]
    feature_mesh_map: dict[str, Any]
    primitive_count: int
    vertex_count: int
    triangle_count: int


# 用途：按四字节边界追加二进制数据，满足 glTF BufferView 对齐要求。
def _append_aligned(buffer: bytearray, content: bytes) -> tuple[int, int]:
    while len(buffer) % 4:
        buffer.append(0)
    offset = len(buffer)
    buffer.extend(content)
    return offset, len(content)


# 用途：校验并打包单个 Face 网格，越界索引和非有限坐标均作为硬错误处理。
def _validated_mesh(mesh: dict[str, Any]) -> tuple[list[list[float]], list[int]]:
    positions = [[float(component) for component in point] for point in mesh.get("positions", [])]
    if any(len(point) != 3 or not all(math.isfinite(value) for value in point) for point in positions):
        raise ValueError("MESH_POSITION_INVALID")
    indices = [int(index) for triangle in mesh.get("indices", []) for index in triangle]
    if len(indices) % 3:
        raise ValueError("MESH_TRIANGLE_INVALID")
    if indices and (min(indices) < 0 or max(indices) >= len(positions)):
        raise ValueError("MESH_INDEX_OUT_OF_RANGE")
    return positions, indices


# 用途：把 glTF JSON 与二进制 Buffer 封装为单文件 GLB 2.0。
def _make_glb(document: dict[str, Any], binary: bytes) -> bytes:
    json_bytes = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
    binary += b"\x00" * ((4 - len(binary) % 4) % 4)
    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary)
    return b"".join([
        struct.pack("<4sII", b"glTF", 2, total_length),
        struct.pack("<I4s", len(json_bytes), b"JSON"), json_bytes,
        struct.pack("<I4s", len(binary), b"BIN\x00"), binary,
    ])


# 用途：生成一 Face 一 Primitive 的 GLB，并建立 Face、Feature 与 Primitive 双向索引。
def build_lightweight_mesh(
    parser_result: dict[str, Any],
    topology: StableTopology,
    feature_geometry_links: list[dict[str, Any]],
) -> LightweightMeshResult:
    source_meshes = []
    for mesh in parser_result.get("meshes", []):
        face_id = topology.source_entity_map.get(str(mesh.get("entity_id", "")))
        if face_id:
            source_meshes.append((face_id, mesh))
    source_meshes.sort(key=lambda item: item[0])

    binary = bytearray()
    buffer_views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    primitives: list[dict[str, Any]] = []
    face_entries: dict[str, Any] = {}
    primitive_to_face: dict[str, str] = {}
    total_vertices = 0
    total_triangles = 0
    for face_id, mesh in source_meshes:
        positions, flat_indices = _validated_mesh(mesh)
        if not positions or not flat_indices:
            continue
        primitive_index = len(primitives)
        position_bytes = b"".join(struct.pack("<fff", *point) for point in positions)
        index_bytes = b"".join(struct.pack("<I", index) for index in flat_indices)
        position_offset, position_length = _append_aligned(binary, position_bytes)
        position_view = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": position_offset,
                             "byteLength": position_length, "target": 34962})
        index_offset, index_length = _append_aligned(binary, index_bytes)
        index_view = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": index_offset,
                             "byteLength": index_length, "target": 34963})
        position_accessor = len(accessors)
        accessors.append({
            "bufferView": position_view, "componentType": 5126, "count": len(positions),
            "type": "VEC3",
            "min": [min(point[axis] for point in positions) for axis in range(3)],
            "max": [max(point[axis] for point in positions) for axis in range(3)],
        })
        index_accessor = len(accessors)
        accessors.append({
            "bufferView": index_view, "componentType": 5125,
            "count": len(flat_indices), "type": "SCALAR",
        })
        primitive_id = stable_id("MESHPRIM", topology.shape_hash, face_id, "lod0")
        primitives.append({
            "attributes": {"POSITION": position_accessor},
            "indices": index_accessor,
            "mode": 4,
            "material": 0,
            "extras": {"face_id": face_id, "mesh_primitive_id": primitive_id},
        })
        triangle_count = len(flat_indices) // 3
        face_entries[face_id] = {
            "mesh_primitive_id": primitive_id,
            "primitive_index": primitive_index,
            "lod": 0,
            "triangle_range": {
                "first_triangle": 0,
                "triangle_count": triangle_count,
                "global_first_triangle": total_triangles,
            },
            "vertex_count": len(positions),
            "triangle_count": triangle_count,
        }
        primitive_to_face[primitive_id] = face_id
        total_vertices += len(positions)
        total_triangles += triangle_count

    document = {
        "asset": {"version": "2.0", "generator": "Cad Feature Center 1.0.0",
                  "extras": {"unit": "mm", "shape_hash": topology.shape_hash}},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "FeatureCenterPart"}],
        "meshes": [{"name": "FacePrimitives", "primitives": primitives}],
        "materials": [{
            "name": "Default",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.72, 0.76, 0.82, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.7,
            },
            "doubleSided": True,
        }],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }
    feature_entries: dict[str, Any] = {}
    for link in feature_geometry_links:
        feature_id = str(link["feature_center_id"])
        face_id = str(link["face_id"])
        face_mesh = face_entries.get(face_id)
        if not face_mesh:
            raise ValueError(f"FEATURE_MESH_FACE_MISSING:{feature_id}:{face_id}")
        entry = feature_entries.setdefault(feature_id, {"face_ids": [], "mesh_primitive_ids": []})
        entry["face_ids"].append(face_id)
        entry["mesh_primitive_ids"].append(face_mesh["mesh_primitive_id"])
    for entry in feature_entries.values():
        entry["face_ids"] = sorted(set(entry["face_ids"]))
        entry["mesh_primitive_ids"] = sorted(set(entry["mesh_primitive_ids"]))

    face_map = {
        "schema_version": "feature_face_mesh_map_v1",
        "shape_hash": topology.shape_hash,
        "lod": 0,
        "mapping_strategy": "one_face_one_primitive",
        "faces": face_entries,
        "primitive_to_face": primitive_to_face,
    }
    feature_map = {
        "schema_version": "feature_mesh_map_v1",
        "shape_hash": topology.shape_hash,
        "features": feature_entries,
    }
    return LightweightMeshResult(
        model_glb=_make_glb(document, bytes(binary)),
        face_mesh_map=face_map,
        feature_mesh_map=feature_map,
        primitive_count=len(primitives),
        vertex_count=total_vertices,
        triangle_count=total_triangles,
    )
