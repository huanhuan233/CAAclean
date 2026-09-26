"""CAA 原生树与 PostgreSQL `cad_entities` 之间的确定性投影。"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Any
from uuid import UUID, uuid5


NATIVE_SOURCE_PREFIX = "caa-native:"


def native_tree_rows(revision_id: UUID, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """把嵌套 CAA 树完整展平为可批量写入 `cad_entities` 的父子有序记录。"""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    stack = list(reversed([(node, "") for node in payload.get("roots") or []]))
    while stack:
        node, inherited_parent_id = stack.pop()
        node_id = str(node.get("node_id") or "")
        if not node_id:
            raise ValueError("native tree node is missing node_id")
        if node_id in seen:
            raise ValueError(f"native tree duplicate node_id: {node_id}")
        seen.add(node_id)
        parent_node_id = str(node.get("parent_id") or inherited_parent_id or "")
        children = list(node.get("children") or [])
        metadata = {key: value for key, value in node.items() if key != "children"}
        metadata.update({"native_tree": True, "native_node_id": node_id, "child_count": len(children)})
        rows.append(
            {
                "id": uuid5(revision_id, node_id),
                "revision_id": revision_id,
                "parent_entity_id": uuid5(revision_id, parent_node_id) if parent_node_id else None,
                "entity_type": _entity_type(node, parent_node_id),
                "source_ref": NATIVE_SOURCE_PREFIX + node_id,
                "source_index": int(node.get("source_index") or 0),
                "name": str(node.get("internal_name") or node.get("display_name") or node_id)[:255],
                "label": str(node.get("display_name") or node_id)[:255],
                "tree_path": str(node.get("tree_path") or f"/{node_id}"),
                "sort_order": len(rows),
                "geometry": {},
                "metadata_json": metadata,
                "fingerprint": node_id,
            }
        )
        for child in reversed(children):
            stack.append((child, node_id))
    expected = int(payload.get("node_count") or len(rows))
    if len(rows) != expected:
        raise ValueError(f"native tree node count mismatch: expected={expected}, actual={len(rows)}")
    return order_native_tree_rows(rows)


def order_native_tree_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate the complete graph and order parents before children for FK writes."""
    by_id = {}
    children = defaultdict(list)
    ready = deque()
    for row in rows:
        entity_id = row["id"]
        if entity_id in by_id:
            raise ValueError(f"native tree duplicate entity id: {entity_id}")
        by_id[entity_id] = row
    for row in rows:
        parent_id = row["parent_entity_id"]
        if parent_id is None:
            ready.append(row)
        elif parent_id not in by_id:
            raise ValueError(
                f"native tree missing parent: node={row['source_ref']}, parent={parent_id}"
            )
        else:
            children[parent_id].append(row)
    ordered = []
    while ready:
        row = ready.popleft()
        ordered.append(row)
        ready.extend(children[row["id"]])
    if len(ordered) != len(rows):
        raise ValueError("native tree contains a parent cycle")
    return ordered


def build_database_tree(entities: Iterable[Any], *, total_node_count: int) -> dict[str, Any]:
    """把数据库查询的一层节点投影为精简 API，不恢复或返回整棵 JSONL。"""
    nodes = []
    for entity in entities:
        metadata = dict(entity.metadata_json or {})
        node = {
            key: value
            for key, value in metadata.items()
            if key not in {"native_tree", "children"}
        }
        node.setdefault("node_id", str(metadata.get("native_node_id") or _source_node_id(entity.source_ref)))
        node.setdefault("parent_id", "")
        node.setdefault("display_name", entity.label or entity.name or node["node_id"])
        node.setdefault("internal_name", entity.name or "")
        node.setdefault("source_index", entity.source_index or 0)
        node.setdefault("tree_path", entity.tree_path)
        node["children"] = []
        nodes.append(node)
    return {
        "schema_version": "caa_native_tree_db_v1",
        "node_count": len(nodes),
        "total_node_count": int(total_node_count),
        "roots": nodes,
    }


def _entity_type(node: dict[str, Any], parent_node_id: str) -> str:
    if not parent_node_id:
        return "root"
    if str(node.get("node_kind") or "") != "product_occurrence":
        return "native_feature"
    startup_type = str(node.get("startup_type") or "").casefold()
    return "part" if startup_type in {"catpart", "mechanicalpart"} else "assembly"


def _source_node_id(source_ref: str | None) -> str:
    value = str(source_ref or "")
    return value[len(NATIVE_SOURCE_PREFIX):] if value.startswith(NATIVE_SOURCE_PREFIX) else value
