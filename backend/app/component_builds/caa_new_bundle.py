from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


_WINDOWS_PATH_RE = re.compile(r"(?i)\b[a-z]:\\[^<>:\"|?*\r\n]+")


class CaaNewBundleError(ValueError):
    pass


class CaaNewBundleReader:
    """Read CAA_NEW normalized reconstruction packages and expose web DTOs."""

    def __init__(self, bundle_dir: Path):
        self.bundle_dir = bundle_dir
        if not (bundle_dir / "manifest.json").is_file():
            raise CaaNewBundleError("CAA_NEW bundle manifest is missing")
        self.manifest = self._read_json("manifest.json")
        schema = str(self.manifest.get("schema_version") or "")
        if not schema.startswith("caa_capture_"):
            raise CaaNewBundleError(f"unsupported CAA_NEW schema: {schema}")

    def build_tree(self, *, include_supplemental: bool = False) -> dict[str, Any]:
        objects = {str(item.get("object_id")): item for item in self._read_jsonl("object_entities.jsonl")}
        property_counts = self._property_counts()
        nodes: dict[str, dict[str, Any]] = {}
        order: dict[str, tuple[int, int, str]] = {}

        for record in self._read_jsonl("product_occurrences.jsonl"):
            node_id = str(record.get("occurrence_id") or "")
            if not node_id:
                continue
            node = self._product_node(record, property_counts)
            nodes[node_id] = node
            order[node_id] = (
                int(record.get("depth") or 0),
                int(record.get("source_index") or 0),
                node_id,
            )

        for record in self._read_jsonl("tree_occurrences.jsonl"):
            if not include_supplemental and str(record.get("presentation_status") or "visible") != "visible":
                continue
            node_id = str(record.get("occurrence_id") or "")
            object_id = str(record.get("object_id") or "")
            if not node_id:
                continue
            node = self._tree_node(record, objects.get(object_id) or {}, property_counts)
            nodes[node_id] = node
            order[node_id] = (
                len(str(record.get("occurrence_path") or record.get("tree_path") or "").split("/")),
                int(record.get("source_index") or 0),
                node_id,
            )

        roots: list[dict[str, Any]] = []
        for node in nodes.values():
            parent = nodes.get(str(node.get("parent_id") or ""))
            if parent is None:
                roots.append(node)
            else:
                parent["children"].append(node)

        self._sort_children(roots, order)
        return {
            "schema_version": self.manifest.get("schema_version"),
            "parser_version": self.manifest.get("parser_version"),
            "capture_status": self.manifest.get("capture_status"),
            "node_count": len(nodes),
            "roots": roots,
        }

    def get_node(self, node_id: str) -> dict[str, Any]:
        flat = self._flat_nodes()
        if node_id not in flat:
            raise CaaNewBundleError(f"native tree node not found: {node_id}")
        return flat[node_id]

    def get_properties(self, node_id: str) -> dict[str, Any]:
        node = self.get_node(node_id)
        subject_ids = self._property_subject_ids(node)
        fields_by_group: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for fact in self._read_jsonl("property_facts.jsonl"):
            if str(fact.get("subject_id") or "") not in subject_ids:
                continue
            tab_id = str(fact.get("tab_id") or "attributes")
            tab_label = str(fact.get("tab_label") or tab_id)
            group_id = str(fact.get("group_id") or "default")
            group_label = str(fact.get("group_label") or group_id)
            fields_by_group[(tab_id, tab_label, group_id, group_label)].append(self._property_field(fact))

        tabs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        tab_display_order: dict[tuple[str, str], int] = {}
        group_display_order: dict[tuple[str, str, str, str], int] = {}
        for (tab_id, tab_label, group_id, group_label), fields in fields_by_group.items():
            fields.sort(key=lambda item: (int(item.get("display_order") or 0), str(item.get("key") or "")))
            group_key = (tab_id, tab_label, group_id, group_label)
            first_order = int(fields[0].get("display_order") or 0) if fields else 0
            tab_key = (tab_id, tab_label)
            tab_display_order[tab_key] = min(tab_display_order.get(tab_key, first_order), first_order)
            group_display_order[group_key] = first_order
            tabs[(tab_id, tab_label)].append(
                {
                    "group_id": group_id,
                    "group_label": group_label,
                    "fields": fields,
                }
            )

        result_tabs = []
        for (tab_id, tab_label), groups in tabs.items():
            groups.sort(
                key=lambda item: (
                    group_display_order.get((tab_id, tab_label, str(item.get("group_id") or ""), str(item.get("group_label") or "")), 0),
                    str(item.get("group_label") or ""),
                )
            )
            result_tabs.append({"tab_id": tab_id, "tab_label": tab_label, "groups": groups})
        result_tabs.sort(
            key=lambda item: (
                tab_display_order.get((str(item.get("tab_id") or ""), str(item.get("tab_label") or "")), 0),
                str(item.get("tab_label") or ""),
            )
        )
        return {
            "node_id": node_id,
            "property_count": sum(len(group["fields"]) for tab in result_tabs for group in tab["groups"]),
            "tabs": result_tabs,
        }

    def get_topology(self) -> dict[str, Any]:
        return {
            "topology_entities": self._read_jsonl("topology_entities.jsonl"),
            "topology_relations": self._read_jsonl("topology_relations.jsonl"),
            "geometry_entities": self._read_jsonl("geometry_entities.jsonl"),
        }

    def get_selection(self, node_id: str) -> dict[str, Any]:
        node = self.get_node(node_id)
        authoritative = {"confirmed", "runtime_matched", "runtime_current_revision", "survives_to_final", "exact", "authoritative"}
        candidates = []
        for record in self._read_jsonl("feature_dependencies.jsonl"):
            if node.get("object_id") and str(record.get("from_object_id") or record.get("object_id") or "") == node["object_id"]:
                status = str(record.get("mapping_status") or record.get("link_status") or "")
                candidates.append({**record, "selectable": status in authoritative})
        return {"node_id": node_id, "candidates": candidates}

    def iter_property_facts(self):
        """逐行读取属性事实，供数据库批量导入，避免把大型 JSONL 整体留在内存。"""
        path = self.bundle_dir / "property_facts.jsonl"
        if not path.is_file():
            return
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                text = line.strip()
                if text:
                    yield json.loads(text)

    def _flat_nodes(self) -> dict[str, dict[str, Any]]:
        flat: dict[str, dict[str, Any]] = {}

        def visit(node: dict[str, Any]) -> None:
            flat[str(node["node_id"])] = {key: value for key, value in node.items() if key != "children"}
            for child in node.get("children") or []:
                visit(child)

        for root in self.build_tree()["roots"]:
            visit(root)
        return flat

    def _product_node(self, record: dict[str, Any], property_counts: dict[str, int]) -> dict[str, Any]:
        node_id = str(record.get("occurrence_id") or "")
        document_id = str(record.get("referenced_document_id") or "")
        reference_id = str(record.get("reference_id") or "")
        name = self._clean_display_name(record.get("instance_name") or record.get("part_number") or node_id)
        return {
            "node_id": node_id,
            "parent_id": str(record.get("parent_occurrence_id") or ""),
            "node_kind": "product_occurrence",
            "display_name": name,
            "internal_name": self._clean_display_name(record.get("part_number") or name),
            "startup_type": "CATProduct" if int(record.get("child_count") or 0) > 0 else "CATPart",
            "document_id": document_id,
            "object_id": "",
            "occurrence_id": node_id,
            "product_occurrence_id": node_id,
            "reference_id": reference_id,
            "referenced_document_id": document_id,
            "source_index": int(record.get("source_index") or 0),
            "tree_path": self._clean_display_name(record.get("tree_path") or ""),
            "occurrence_path": self._clean_display_name(record.get("occurrence_path") or ""),
            "update_status": str(record.get("load_status") or ""),
            "presentation_status": str(record.get("presentation_status") or "visible"),
            "has_children": int(record.get("child_count") or 0) > 0,
            "has_properties": any(property_counts.get(subject, 0) for subject in (node_id, reference_id, document_id)),
            "property_count": sum(property_counts.get(subject, 0) for subject in (node_id, reference_id, document_id)),
            "has_geometry": False,
            "has_topology_mapping": False,
            "geometry_ids": [],
            "topology_ids": [],
            "children": [],
        }

    def _tree_node(self, record: dict[str, Any], obj: dict[str, Any], property_counts: dict[str, int]) -> dict[str, Any]:
        node_id = str(record.get("occurrence_id") or "")
        object_id = str(record.get("object_id") or "")
        product_occurrence_id = str(record.get("product_occurrence_id") or "")
        reference_id = str(record.get("reference_id") or "")
        document_id = str(record.get("document_id") or obj.get("document_id") or "")
        topology_ids = self._string_list(record.get("topology_ids"))
        geometry_ids = self._string_list(record.get("geometry_ids"))
        display_name = self._clean_display_name(obj.get("display_name") or record.get("tree_path") or node_id)
        return {
            "node_id": node_id,
            "parent_id": str(record.get("parent_occurrence_id") or ""),
            "node_kind": str(record.get("occurrence_kind") or obj.get("object_kind") or "native_feature"),
            "display_name": display_name,
            "internal_name": self._clean_display_name(obj.get("internal_name") or display_name),
            "startup_type": str(obj.get("startup_type") or ""),
            "document_id": document_id,
            "object_id": object_id,
            "occurrence_id": node_id,
            "product_occurrence_id": product_occurrence_id,
            "reference_id": reference_id,
            "referenced_document_id": str(record.get("referenced_document_id") or ""),
            "source_index": int(record.get("source_index") or 0),
            "tree_path": self._clean_display_name(record.get("tree_path") or ""),
            "occurrence_path": self._clean_display_name(record.get("occurrence_path") or ""),
            "update_status": str(obj.get("update_status") or ""),
            "presentation_status": str(record.get("presentation_status") or "visible"),
            "has_children": False,
            "has_properties": any(property_counts.get(subject, 0) for subject in (node_id, object_id, document_id)),
            "property_count": sum(property_counts.get(subject, 0) for subject in (node_id, object_id, document_id)),
            "has_geometry": bool(geometry_ids),
            "has_topology_mapping": bool(topology_ids),
            "geometry_ids": geometry_ids,
            "topology_ids": topology_ids,
            "children": [],
        }

    def _property_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for fact in self._read_jsonl("property_facts.jsonl"):
            subject = str(fact.get("subject_id") or "")
            if subject:
                counts[subject] += 1
        return dict(counts)

    @staticmethod
    def _property_subject_ids(node: dict[str, Any]) -> set[str]:
        return {
            str(value)
            for value in (
                node.get("node_id"),
                node.get("occurrence_id"),
                node.get("object_id"),
                node.get("product_occurrence_id"),
                node.get("reference_id"),
                node.get("document_id"),
                node.get("referenced_document_id"),
            )
            if value
        }

    def _property_field(self, fact: dict[str, Any]) -> dict[str, Any]:
        display_value = self._redact_value(fact.get("display_value"))
        raw_value = self._redact_value(fact.get("raw_value"))
        return {
            "property_id": str(fact.get("property_id") or ""),
            "key": str(fact.get("key") or ""),
            "display_name": str(fact.get("display_name") or fact.get("key") or ""),
            "raw_value": raw_value,
            "raw_unit": str(fact.get("raw_unit") or ""),
            "display_value": display_value,
            "display_unit": str(fact.get("display_unit") or ""),
            "value_type": str(fact.get("value_type") or ""),
            "source_api": str(fact.get("source_api") or ""),
            "read_status": str(fact.get("read_status") or ""),
            "authority": str(fact.get("authority") or ""),
            "display_order": int(fact.get("display_order") or 0),
            "read_only": bool(fact.get("read_only")),
        }

    def _read_json(self, relative_path: str) -> dict[str, Any]:
        path = self.bundle_dir / relative_path
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def _read_jsonl(self, relative_path: str) -> list[dict[str, Any]]:
        path = self.bundle_dir / relative_path
        if not path.is_file():
            return []
        records = []
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                text = line.strip()
                if text:
                    records.append(json.loads(text))
        return records

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if value in (None, ""):
            return []
        return [str(value)]

    @classmethod
    def _clean_display_name(cls, value: Any) -> str:
        text = str(value or "")
        if re.match(r"(?i)^[a-z]:\\", text):
            return Path(text).name
        return cls._redact_value(text)

    @staticmethod
    def _redact_value(value: Any) -> Any:
        if not isinstance(value, str):
            return value

        def replace(match: re.Match[str]) -> str:
            return f"<local_path>\\{Path(match.group(0)).name}"

        return _WINDOWS_PATH_RE.sub(replace, value)

    def _sort_children(self, nodes: list[dict[str, Any]], order: dict[str, tuple[int, int, str]]) -> None:
        nodes.sort(key=lambda node: order.get(str(node.get("node_id")), (0, 0, str(node.get("node_id")))))
        for node in nodes:
            children = node.get("children") or []
            node["has_children"] = bool(children)
            self._sort_children(children, order)
