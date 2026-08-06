"""把现有 CAD 结构树投影为 STEP/CATPart 共用的只读 BOM 契约。"""

from __future__ import annotations


PART_NODE_TYPES = {"part", "imported_object"}


# 用途：构建前端可稳定消费的 BOM；不凭文件名或样件内容伪造装配节点。
def build_bom_contract(roots: list[dict], source_format: str) -> dict:
    normalized = [_normalize_node(node, source_format.upper(), level=0) for node in roots]
    part_count = sum(_count_parts(node) for node in normalized)
    has_assembly = any(_contains_assembly(node) for node in normalized) or part_count > 1
    if not normalized:
        assembly_mode = "none"
    elif has_assembly:
        assembly_mode = "assembly"
    else:
        assembly_mode = "single_part"
    return {
        "assembly_mode": assembly_mode,
        "default_visible": assembly_mode == "assembly",
        "part_count": part_count,
        "nodes": normalized,
    }


# 用途：递归补齐统一字段，同时保留真实 placement 和后端已提供的 Primitive 映射。
def _normalize_node(node: dict, source_format: str, level: int) -> dict:
    metadata = dict(node.get("metadata") or {})
    node_id = str(node.get("id") or node.get("node_id") or "")
    source_ref = str(node.get("source_ref") or "")
    entity_type = str(node.get("entity_type") or node.get("node_type") or "part")
    children = [_normalize_node(child, source_format, level + 1) for child in (node.get("children") or [])]
    own_primitives = _unique_strings(metadata.get("mesh_primitive_ids") or [])
    own_entities = _unique_strings(metadata.get("entity_ids") or ([node_id] if node_id else []))
    descendant_primitives = _unique_strings(
        own_primitives +
        [primitive_id for child in children for primitive_id in child.get("descendant_mesh_primitive_ids", [])]
    )
    descendant_entities = _unique_strings(
        own_entities +
        [entity_id for child in children for entity_id in child.get("descendant_entity_ids", [])]
    )
    return {
        "node_id": node_id,
        "parent_id": str(node.get("parent_entity_id") or node.get("parent_id") or ""),
        "name": str(node.get("label") or node.get("name") or source_ref or entity_type),
        "part_number": str(metadata.get("part_number") or source_ref or ""),
        "instance_name": str(metadata.get("instance_name") or source_ref or ""),
        "version": str(metadata.get("version") or ""),
        "material": str(metadata.get("material") or ""),
        "node_type": entity_type,
        "quantity": max(1, int(metadata.get("quantity") or 1)),
        "source_format": source_format,
        "level": level,
        "transform": node.get("placement") or metadata.get("transform"),
        "mesh_primitive_ids": own_primitives,
        "descendant_mesh_primitive_ids": descendant_primitives,
        "entity_ids": own_entities,
        "descendant_entity_ids": descendant_entities,
        "solid_count": int(metadata.get("solid_count") or (1 if entity_type == "solid" else 0)),
        "volume": node.get("volume") or metadata.get("volume"),
        "bounding_box": node.get("bounding_box") or metadata.get("bounding_box"),
        "assembly_path": str(metadata.get("assembly_path") or ""),
        "constraint_status": str(metadata.get("constraint_status") or ""),
        "constraint_count": metadata.get("constraint_count"),
        "children": children,
    }


def _unique_strings(values: list) -> list[str]:
    return sorted({str(value) for value in values if value})


# 用途：统计真实 part/imported_object 节点；旧单零件树没有 Part 节点时以一个根模型兼容。
def _count_parts(node: dict) -> int:
    own = 1 if node["node_type"] in PART_NODE_TYPES else 0
    child_count = sum(_count_parts(child) for child in node["children"])
    if node["level"] == 0 and own == 0 and child_count == 0:
        return 1
    return own + child_count


# 用途：识别后端明确给出的 assembly/subassembly，不从视觉或名称猜装配语义。
def _contains_assembly(node: dict) -> bool:
    return node["node_type"] in {"assembly", "subassembly"} or any(_contains_assembly(child) for child in node["children"])
