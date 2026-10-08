"""Definition-level composite projection from captured R21 objects and facts.

Tree occurrences locate a definition; they never establish laminate order.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any, Iterable


_KINDS = {
    "CATCompStacking": "stacking",
    "CATCompPliesGroup": "group",
    "CATCompSequence": "sequence",
    "CATCompPly": "ply",
    "CATCompCutPiece": "cut_piece",
    "CATCompCutPiecesGroup": "cut_piece_group",
}
_ORDERED_PARENTS = frozenset({"stacking", "group", "sequence"})
_LENGTH_KEYS = frozenset({"composite_cured_thickness", "composite_uncured_thickness", "composite_material_width"})
_AREA_KEYS = frozenset({"composite_area_m2"})


def _field(fact: dict[str, Any]) -> dict[str, Any]:
    key = str(fact.get("key") or "")
    unit = str(fact.get("raw_unit") or "")
    status = str(fact.get("read_status") or "unknown")
    value: float | None = None
    normalized_unit = ""
    if status == "available" and (key in _LENGTH_KEYS or key in _AREA_KEYS or key == "composite_orientation"):
        try:
            number = float(fact["raw_value"])
            if math.isfinite(number):
                if key in _LENGTH_KEYS and unit in {"m", "mm"}:
                    value, normalized_unit = (number * 1000 if unit == "m" else number), "mm"
                elif key in _AREA_KEYS and unit in {"m2", "m²", "mm2", "mm²"}:
                    value, normalized_unit = (number * 1_000_000 if unit in {"m2", "m²"} else number), "mm²"
                elif key == "composite_orientation" and unit in {"rad", "deg", "°"}:
                    value, normalized_unit = (math.degrees(number) if unit == "rad" else number), "deg"
        except (ValueError, TypeError, KeyError):
            pass
    return {
        "raw_value": fact.get("raw_value"), "raw_unit": unit,
        "raw_display_text": fact.get("raw_display_text"),
        "normalized_value": value, "normalized_unit": normalized_unit,
        "read_status": status, "source_api": fact.get("source_api"),
        "property_id": fact.get("property_id"),
    }


def build_composite_structure(
    objects: Iterable[dict[str, Any]], occurrences: Iterable[dict[str, Any]],
    facts: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve physical ply identity, provenance and only verified native ordering."""
    entities: dict[str, dict[str, Any]] = {}
    for source in objects:
        kind = _KINDS.get(str(source.get("startup_type") or ""))
        object_id = str(source.get("object_id") or "")
        if kind and object_id:
            if object_id in entities:
                raise ValueError(f"duplicate composite object id: {object_id}")
            entities[object_id] = {
                "object_id": object_id, "kind": kind,
                "document_id": source.get("document_id"),
                "display_name": source.get("display_name"),
                "startup_type": source.get("startup_type"),
                "update_status": source.get("update_status") or "unknown",
                "identity": source.get("identity"),
                "occurrence_ids": [], "occurrence_paths": [], "parent_object_ids": [],
                "ordered_child_object_ids": None, "order_status": "unavailable",
                "fields": {}, "diagnostics": [],
            }
    occurrence_by_id: dict[str, dict[str, Any]] = {}
    placements: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for occurrence in occurrences:
        occurrence_id = str(occurrence.get("occurrence_id") or "")
        if occurrence_id:
            if occurrence_id in occurrence_by_id:
                raise ValueError(f"duplicate composite occurrence id: {occurrence_id}")
            occurrence_by_id[occurrence_id] = occurrence
        object_id = str(occurrence.get("object_id") or "")
        if object_id in entities:
            placements[object_id].append(occurrence)
    for object_id, row in entities.items():
        seen_parents: set[str] = set()
        for occurrence in placements[object_id]:
            occurrence_id = str(occurrence.get("occurrence_id") or "")
            if occurrence_id:
                row["occurrence_ids"].append(occurrence_id)
            path = occurrence.get("tree_path")
            if path and path not in row["occurrence_paths"]:
                row["occurrence_paths"].append(path)
            parent = occurrence_by_id.get(str(occurrence.get("parent_occurrence_id") or "")) or {}
            parent_id = str(parent.get("object_id") or "")
            if parent_id in entities and parent_id not in seen_parents:
                seen_parents.add(parent_id)
                row["parent_object_ids"].append(parent_id)
    for fact in facts:
        row = entities.get(str(fact.get("subject_id") or ""))
        key = str(fact.get("key") or "")
        if row is None or not key.startswith("composite_"):
            continue
        if key in row["fields"]:
            row["diagnostics"].append(f"duplicate_property:{key}")
            continue
        row["fields"][key] = _field(fact)
    for row in entities.values():
        if row["kind"] not in _ORDERED_PARENTS:
            continue
        order_fact = row["fields"].get("composite_native_ordered_child_ids")
        if not order_fact or order_fact["read_status"] not in {"available", "partial"}:
            continue
        try:
            ids = json.loads(order_fact["raw_value"])
        except (TypeError, ValueError):
            row["diagnostics"].append("invalid_native_order_payload")
            continue
        if not isinstance(ids, list) or any(value is not None and not isinstance(value, str) for value in ids):
            row["diagnostics"].append("invalid_native_order_payload")
            continue
        if len([value for value in ids if value is not None]) != len(set(value for value in ids if value is not None)):
            row["diagnostics"].append("duplicate_native_order_member")
            continue
        row["ordered_child_object_ids"] = ids
        unresolved = any(value is None or value not in entities for value in ids)
        if unresolved:
            row["diagnostics"].append("unresolved_native_order_member")
        row["order_status"] = "partial" if unresolved or order_fact["read_status"] == "partial" else "native_complete"
    for row in entities.values():
        if row["kind"] != "ply":
            continue
        from app.component_builds.composite_boundaries import assess_native_boundaries
        surface_fact = row["fields"].get("composite_surface_native_boundary_loops")
        contour_fact = row["fields"].get("composite_contour_native_boundary_loops")
        selected_boundary = surface_fact if surface_fact and surface_fact["read_status"] in {"available", "partial"} else contour_fact
        if selected_boundary and selected_boundary["read_status"] in {"available", "partial"}:
            try:
                boundary_payload = json.loads(selected_boundary["raw_value"])
            except (ValueError, TypeError):
                boundary_payload = None
            row["boundary"] = assess_native_boundaries(boundary_payload, selected_boundary["read_status"])
            row["boundary"]["geometry_role"] = "ply_surface" if selected_boundary is surface_fact else "ply_contour"
        else:
            row["boundary"] = {"status": "unavailable", "geometry_role": "unknown",
                               "diagnostics": ["native_ordered_boundary_not_captured"]}
        if contour_fact and contour_fact["read_status"] == "available":
            from app.component_builds.composite_regions import derive_planar_regions
            try:
                contour_payload = json.loads(contour_fact["raw_value"])
            except (ValueError, TypeError):
                contour_payload = None
            row["contour_planar_region"] = derive_planar_regions(contour_payload)
        else:
            row["contour_planar_region"] = {"status": "unavailable", "diagnostics": ["ordered_contour_not_captured"]}
        row["render_status"] = "unavailable_without_verified_ply_mesh"
        pieces_fact = row["fields"].get("composite_cut_piece_object_ids")
        if not pieces_fact or pieces_fact["read_status"] not in {"available", "partial"}:
            row["cut_piece_object_ids"] = None
            continue
        try:
            piece_ids = json.loads(pieces_fact["raw_value"])
            if not isinstance(piece_ids, list) or any(item is not None and not isinstance(item, str) for item in piece_ids):
                raise ValueError("invalid cut piece list")
        except (ValueError, TypeError):
            row["diagnostics"].append("invalid_cut_piece_payload")
            row["cut_piece_object_ids"] = None
            continue
        row["cut_piece_object_ids"] = piece_ids
        for piece_id in piece_ids:
            piece = entities.get(piece_id)
            if piece and piece["kind"] == "cut_piece":
                if row["object_id"] not in piece["parent_object_ids"]:
                    piece["parent_object_ids"].append(row["object_id"])
            elif piece_id is not None:
                row["diagnostics"].append(f"unresolved_cut_piece:{piece_id}")
    return list(entities.values())
