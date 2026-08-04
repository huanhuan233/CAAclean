"""把现有 FreeCAD 解析结果转换为稳定 Feature Center 拓扑。"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .contracts import stable_id


_VOLATILE_ENTITY_KEYS = {
    "id", "revision_id", "parent_entity_id", "source_ref", "source_index",
    "tree_path", "sort_order",
}
_ENTITY_PREFIXES = {
    "solid": "SOLID",
    "shell": "SHELL",
    "face": "FACE",
    "wire": "WIRE",
    "edge": "EDGE",
    "vertex": "VERTEX",
}


@dataclass(frozen=True)
class StableTopology:
    """保存稳定拓扑、关系、旧编号映射、形状哈希和统一容差。"""

    shape_hash: str
    tolerance_mm: float
    entities: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    source_entity_map: dict[str, str]


# 用途：规范化浮点噪声；精度只用于指纹，不会覆盖权威测量原值。
def _canonical_value(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("BREP_VALUE_NONFINITE：拓扑指纹包含非有限数值")
        return round(value, 9)
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    return value


# 用途：生成不含 revision UUID、Face 序号和进程状态的实体几何指纹文本。
def _entity_signature(entity: dict[str, Any]) -> str:
    semantic = {
        key: value for key, value in entity.items()
        if key not in _VOLATILE_ENTITY_KEYS
    }
    return json.dumps(
        _canonical_value(semantic), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


# 用途：根据零件包围盒对角线计算统一容差，绝对下限用于小尺度模型数值稳定。
def _model_tolerance(bounding_box: dict[str, Any] | None) -> float:
    if not bounding_box:
        return 0.01
    minimum = bounding_box.get("min", [0.0, 0.0, 0.0])
    maximum = bounding_box.get("max", [0.0, 0.0, 0.0])
    diagonal = math.sqrt(sum((float(maximum[i]) - float(minimum[i])) ** 2 for i in range(3)))
    return max(0.01, diagonal * 1.0e-5)


# 用途：建立 Shape Hash；其稳定范围限定为相同几何、相同算法版本和相同 Kernel 提取语义。
def _shape_hash(entities: list[dict[str, Any]], relations: list[dict[str, Any]]) -> str:
    signatures = {entity["id"]: _entity_signature(entity) for entity in entities}
    entity_lines = sorted(signatures.values())
    relation_lines = sorted(
        json.dumps(
            [
                relation.get("relation_type", "unknown"),
                signatures.get(relation.get("source_entity_id", ""), "missing"),
                signatures.get(relation.get("target_entity_id", ""), "missing"),
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for relation in relations
    )
    payload = "\n".join(entity_lines + relation_lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# 用途：把 FreeCAD 的 revision-local 编号转换为 Shape Hash 范围内稳定的拓扑编号和关系。
def build_stable_topology(parser_result: dict[str, Any]) -> StableTopology:
    entities = list(parser_result.get("entities", []))
    relations = list(parser_result.get("relations", []))
    shape_hash = _shape_hash(entities, relations)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        entity_type = str(entity.get("entity_type", "unknown"))
        grouped[(entity_type, _entity_signature(entity))].append(entity)

    source_map: dict[str, str] = {}
    stable_entities: list[dict[str, Any]] = []
    for (entity_type, signature), occurrences in sorted(grouped.items()):
        # 完全对称实体无法只靠几何区分，最后使用 Kernel 的稳定枚举位置分配 occurrence。
        occurrences.sort(key=lambda item: (
            -1 if item.get("source_index") is None else int(item["source_index"]),
            str(item.get("source_ref") or ""),
        ))
        for occurrence, entity in enumerate(occurrences):
            prefix = _ENTITY_PREFIXES.get(entity_type, "TOPO")
            entity_id = stable_id(prefix, shape_hash, signature, str(occurrence))
            source_map[str(entity["id"])] = entity_id
            stable_entity = {
                key: _canonical_value(value) for key, value in entity.items()
                if key not in _VOLATILE_ENTITY_KEYS
            }
            stable_entity["entity_id"] = entity_id
            stable_entity["topology_fingerprint"] = hashlib.sha256(
                signature.encode("utf-8")
            ).hexdigest()
            stable_entities.append(stable_entity)

    stable_relations: list[dict[str, Any]] = []
    seen_relations: set[tuple[str, str, str]] = set()
    for relation in relations:
        source_id = source_map.get(str(relation.get("source_entity_id", "")))
        target_id = source_map.get(str(relation.get("target_entity_id", "")))
        if not source_id or not target_id:
            raise ValueError(
                "BREP_TOPOLOGY_RELATION_DANGLING："
                f"{relation.get('relation_type', 'unknown')}"
            )
        relation_type = str(relation.get("relation_type", "unknown"))
        key = (relation_type, source_id, target_id)
        if key in seen_relations:
            continue
        seen_relations.add(key)
        stable_relations.append({
            "relation_id": stable_id("TOPOREL", shape_hash, *key),
            "relation_type": relation_type,
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "attributes": _canonical_value(relation.get("attributes", {})),
        })

    stable_entities.sort(key=lambda item: item["entity_id"])
    stable_relations.sort(key=lambda item: item["relation_id"])
    return StableTopology(
        shape_hash=shape_hash,
        tolerance_mm=_model_tolerance(parser_result.get("bounding_box")),
        entities=stable_entities,
        relations=stable_relations,
        source_entity_map=source_map,
    )
