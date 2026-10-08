from __future__ import annotations

import json
import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


_WINDOWS_PATH_RE = re.compile(r"(?i)\b[a-z]:\\[^<>:\"|?*\r\n]+")

NATIVE_EVIDENCE_FILES = {
    "features": "features.jsonl",
    "native_features": "native_features.jsonl",
    "topology_entities": "topology_entities.jsonl",
    "topology_relations": "topology_relations.jsonl",
    "topology_bodies": "native_topology_bodies.jsonl",
    "topology_cells": "native_topology_cells.jsonl",
    "topology_wires": "native_topology_wires.jsonl",
    "topology_coedges": "native_topology_coedges.jsonl",
    "feature_topology_links": "native_feature_topology_links.jsonl",
    "feature_dependencies": "feature_dependencies.jsonl",
    "geometry_entities": "geometry_entities.jsonl",
    "pmi_entities": "pmi_entities.jsonl",
    "pmi_associations": "pmi_associations.jsonl",
    "fta_sets": "fta_sets.jsonl",
    "fta_semantics": "fta_semantics.jsonl",
    "canonical_features": "canonical_features.jsonl",
    "measurements": "measurements.jsonl",
    "topology_faces": "topology_faces.jsonl",
    "feature_geometry_links": "feature_geometry_links.jsonl",
    "selection_index": "selection_index.json",
    # Derived from object definitions, occurrences and raw property facts.
    "composite_structure": "object_entities.jsonl",
}

_TOPOLOGY_KINDS = frozenset({"body", "solid", "volume", "face", "edge", "vertex", "wire", "loop", "coedge"})
_TOPOLOGY_ALIASES = {"lump": "solid", "oriented_edge": "coedge"}


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
        if schema not in {"caa_capture_v1", "cad_parse_mvp_v11"}:
            raise CaaNewBundleError(f"unsupported CAA_NEW schema: {schema}")
        self.schema = schema
        self.diagnostics: list[dict[str, str]] = []

    def iter_canonical_native_features(self):
        """Return definition-level native semantics, hiding capture projections and legacy field names."""
        objects = {}
        occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
        facets = {}
        if self.schema == "caa_capture_v1":
            objects = {str(row.get("object_id")): row for row in self._read_jsonl("object_entities.jsonl")}
            for row in self._read_jsonl("tree_occurrences.jsonl"):
                occurrences[str(row.get("object_id") or "")].append(row)
            facets = {str(row.get("facet_id")): row for row in self._read_jsonl("semantic_facets.jsonl")}
        seen: set[str] = set()
        for row in self._iter_jsonl_required("native_features.jsonl"):
            if self.schema == "caa_capture_v1":
                object_id = str(row.get("feature_id") or "")
                if not object_id:
                    raise CaaNewBundleError("native_features.jsonl: missing feature_id")
                facet_id = str(row.get("native_feature_id") or "")
                facet = facets.get(facet_id)
                if facet and (str(facet.get("subject_id") or "") != object_id or
                              str(facet.get("decoder_id") or "") != str(row.get("decoder_id") or "")):
                    self.diagnostics.append({"code": "semantic_projection_conflict", "facet_id": facet_id,
                                             "object_id": object_id})
                obj = objects.get(object_id) or {}
                placements = occurrences.get(object_id) or []
                record = dict(row)
                record.update({
                    "feature_id": object_id,
                    "object_id": object_id,
                    "document_id": str(obj.get("document_id") or (placements[0].get("document_id") if placements else "") or ""),
                    "occurrence_ids": sorted({str(item["occurrence_id"]) for item in placements if item.get("occurrence_id")}),
                    "product_occurrence_ids": sorted({str(item["product_occurrence_id"]) for item in placements if item.get("product_occurrence_id")}),
                    "update_status": str(obj.get("update_status") or row.get("update_status") or "unknown"),
                    "source_schema": self.schema,
                    "source_facet_id": facet_id,
                })
                record["coordinate_frame"] = "part_local" if record["product_occurrence_ids"] else "document"
            else:
                object_id = str(row.get("source_object_id") or row.get("native_feature_id") or "")
                if not object_id:
                    raise CaaNewBundleError("native_features.jsonl: missing source_object_id")
                record = dict(row)
                record.update({
                    "feature_id": object_id,
                    "object_id": object_id,
                    "decoder_id": str(row.get("decoder") or ""),
                    "decode_status": str(row.get("decoder_status") or "unknown"),
                    "document_id": "",
                    "occurrence_ids": [],
                    "product_occurrence_ids": [str(row["instance_id"])] if row.get("instance_id") else [],
                    "source_schema": self.schema,
                    "coordinate_frame": "part_local" if row.get("instance_id") else "document",
                })
            if object_id in seen:
                raise CaaNewBundleError(f"native_features.jsonl: duplicate object: {object_id}")
            seen.add(object_id)
            yield record

    def semantic_summary(self) -> dict[str, Any]:
        """按定义级对象计数，不把树实例或兼容投影算作新增专用特征。"""
        summary: dict[str, Any] = {
            "definition_count": 0, "typed_count": 0, "type_only_count": 0,
            "generic_count": 0, "failed_count": 0, "unavailable_count": 0,
            "typed_by_decoder": {},
        }
        for record in self.iter_canonical_native_features():
            summary["definition_count"] += 1
            level = str(record.get("decode_level") or "")
            status = str(record.get("decode_status") or "")
            if status in {"failed", "error", "rejected"}:
                summary["failed_count"] += 1
            elif level == "typed":
                summary["typed_count"] += 1
                decoder = str(record.get("decoder_id") or "unknown")
                summary["typed_by_decoder"][decoder] = summary["typed_by_decoder"].get(decoder, 0) + 1
            elif level == "type_only":
                summary["type_only_count"] += 1
            elif level == "generic":
                summary["generic_count"] += 1
            else:
                summary["unavailable_count"] += 1
        return summary

    def native_evidence_streams(self):
        """Expose only present capture channels; typed semantics have one canonical projection."""
        self._validate_mbd_channels()
        streams = {}
        for kind, filename in NATIVE_EVIDENCE_FILES.items():
            if kind == "composite_structure":
                if self.has_composite_source():
                    streams[kind] = self.composite_structure()
                continue
            if kind in {"canonical_features", "measurements", "topology_faces", "feature_geometry_links", "selection_index"}:
                continue
            if not (self.bundle_dir / filename).is_file():
                continue
            if kind == "native_features":
                streams[kind] = self.iter_canonical_native_features()
            elif kind == "topology_entities":
                streams[kind] = self.iter_topology_entities()
            elif kind == "topology_cells":
                streams[kind] = self.iter_topology_cells()
            elif kind == "fta_semantics":
                streams[kind] = self.iter_fta_semantics()
            else:
                streams[kind] = self._iter_jsonl_required(filename)
        connection_files = ("object_entities.jsonl", "tree_occurrences.jsonl", "property_facts.jsonl",
                            "product_occurrences.jsonl")
        if all((self.bundle_dir / name).is_file() for name in connection_files):
            from app.assembly.connection_semantics import build_connection_semantics
            connections = build_connection_semantics(*(self._read_jsonl(name) for name in connection_files))
            streams["connection_semantics"] = connections
            streams["connection_semantics_status"] = [{
                "source_channel_status": "captured",
                "connection_count": len(connections),
                "rule_version": "customer.connection.v1",
                "geometry_association_status": "unresolved",
            }]
        return streams

    def has_composite_source(self) -> bool:
        return all((self.bundle_dir / name).is_file() for name in
                   ("object_entities.jsonl", "tree_occurrences.jsonl", "property_facts.jsonl"))

    def composite_structure(self) -> list[dict[str, Any]]:
        if not self.has_composite_source():
            raise CaaNewBundleError("composite source records are incomplete")
        from app.component_builds.composite_projection import build_composite_structure
        names = ("object_entities.jsonl", "tree_occurrences.jsonl", "property_facts.jsonl")
        return build_composite_structure(*(self._read_jsonl(name) for name in names))

    def iter_fta_semantics(self):
        """Expose typed display/search fields without changing the raw CAA semantic payload."""
        for row in self._iter_jsonl_required("fta_semantics.jsonl"):
            payload = row.get("semantic_payload") or {}
            if not isinstance(payload, dict):
                raise CaaNewBundleError("fta_semantics.jsonl: semantic_payload must be an object")
            normalized = dict(row)
            for key in ("native_alias", "annotation_ttrs_count", "annotation_ttrs_status",
                        "native_geometry_link_status"):
                if key not in normalized and key in payload:
                    normalized[key] = payload[key]
            yield normalized

    def _validate_mbd_channels(self) -> None:
        """Reject broken PMI identity and declared checksums before replacing a revision snapshot."""
        files = ("pmi_entities.jsonl", "pmi_associations.jsonl", "fta_semantics.jsonl", "fta_sets.jsonl")
        declared = self.manifest.get("output_files") or {}
        present = {name for name in files if (self.bundle_dir / name).is_file()}
        expected_counts = {
            "pmi_entities.jsonl": self.manifest.get("pmi_count"),
            "pmi_associations.jsonl": self.manifest.get("pmi_association_count"),
        }
        for name in files:
            if name in declared and name not in present:
                raise CaaNewBundleError(f"MBD declared artifact missing: {name}")
            count = expected_counts.get(name)
            if isinstance(count, int) and count > 0 and name not in present:
                raise CaaNewBundleError(f"MBD counted artifact missing: {name}")
        if not present:
            return
        for name in present:
            expected = (declared.get(name) or {}).get("sha256")
            if expected and hashlib.sha256((self.bundle_dir / name).read_bytes()).hexdigest() != expected:
                raise CaaNewBundleError(f"MBD artifact hash mismatch: {name}")
        nodes = self._mbd_ids("pmi_entities.jsonl", "pmi_id") if files[0] in present else set()
        annotations = self._mbd_ids("fta_semantics.jsonl", "fta_semantic_id") if files[2] in present else set()
        for name, ids in ((files[0], nodes), (files[2], annotations)):
            count = expected_counts.get(name)
            if isinstance(count, int) and count != len(ids):
                raise CaaNewBundleError(f"{name}: manifest count mismatch: {count} != {len(ids)}")
        if files[0] in present and files[2] in present:
            for record in self._iter_jsonl_required(files[2]):
                owner = str(record.get("fta_set_id") or "")
                if owner and owner not in nodes:
                    raise CaaNewBundleError(f"fta_semantics.jsonl: unknown fta_set_id: {owner}")
        if files[1] in present:
            known = nodes | annotations
            relation_count = 0
            for record in self._iter_jsonl_required(files[1]):
                relation_count += 1
                source, target = str(record.get("pmi_id") or ""), str(record.get("target_id") or "")
                if source not in known or target not in known:
                    raise CaaNewBundleError(f"pmi_associations.jsonl: unresolved endpoint: {source} -> {target}")
            declared_count = expected_counts.get(files[1])
            if isinstance(declared_count, int) and relation_count != declared_count:
                raise CaaNewBundleError(f"{files[1]}: manifest count mismatch")
        if files[3] in present:
            set_ids = self._mbd_ids(files[3], "fta_set_id")
            if files[0] in present and not set_ids.issubset(nodes):
                raise CaaNewBundleError("fta_sets.jsonl: unknown PMI set identity")

    def _mbd_ids(self, filename: str, field: str) -> set[str]:
        result: set[str] = set()
        for record in self._iter_jsonl_required(filename):
            value = str(record.get(field) or "")
            if not value or value in result:
                raise CaaNewBundleError(f"{filename}: missing or duplicate {field}: {value}")
            result.add(value)
        return result

    def iter_topology_entities(self):
        """Normalize native topology kinds without erasing the capture-side type."""
        for row in self._iter_jsonl_required("topology_entities.jsonl"):
            yield self._normalize_topology_kind(row)

    def iter_topology_cells(self):
        """Return cell records with the same stable kind contract as topology entities."""
        for row in self._iter_jsonl_required("native_topology_cells.jsonl"):
            yield self._normalize_topology_kind(row)

    @staticmethod
    def _normalize_topology_kind(row: dict[str, Any]) -> dict[str, Any]:
        """Keep unknown source terms visible while refusing to classify them as a known CAD type."""
        raw_kind = str(row.get("topology_kind") or row.get("kind") or row.get("topology_type") or "")
        canonical = _TOPOLOGY_ALIASES.get(raw_kind.lower(), raw_kind.lower())
        return {**row, "kind": canonical if canonical in _TOPOLOGY_KINDS else "unknown", "raw_topology_kind": raw_kind}

    def _iter_jsonl_required(self, relative_path: str):
        path = self.bundle_dir / relative_path
        if not path.is_file():
            raise CaaNewBundleError(f"required capture artifact missing: {relative_path}")
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CaaNewBundleError(f"{relative_path}:{line_number}: invalid JSON") from exc
                if not isinstance(record, dict):
                    raise CaaNewBundleError(f"{relative_path}:{line_number}: expected object")
                yield record

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

        tree_records = self._read_jsonl("tree_occurrences.jsonl")
        tree_by_id = {str(record.get("occurrence_id") or ""): record for record in tree_records}
        visible_cache: dict[str, bool] = {}

        def visible_in_primary_tree(record: dict[str, Any], ancestors: set[str] | None = None) -> bool:
            node_id = str(record.get("occurrence_id") or "")
            if node_id in visible_cache:
                return visible_cache[node_id]
            if str(record.get("presentation_status") or "visible") != "visible":
                visible_cache[node_id] = False
                return False
            ancestors = (ancestors or set()) | {node_id}
            parent_id = str(record.get("parent_occurrence_id") or "")
            parent = tree_by_id.get(parent_id)
            # A missing parent is handled by the existing root behavior; a cycle is invalid.
            visible = parent_id not in ancestors and (
                parent is None or visible_in_primary_tree(parent, ancestors)
            )
            visible_cache[node_id] = visible
            return visible

        for record in tree_records:
            if not include_supplemental and not visible_in_primary_tree(record):
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
