"""Customer R/DM connection facts from captured native objects and tree membership.

This module never infers a connection from display names or B-Rep appearance.
Alias and CATIA interface markers are independent captured facts.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
import math
from typing import Any


RULE_VERSION = "customer.connection.v1"
ROOT_ALIASES = {"连接定义": "fastener", "K_密封定义": "seal", "M_胶接定义": "bond"}
SEAL_BOND_KEYS = {*(f"K{i:03d}" for i in range(1, 8)),
                  *(f"K{i:03d}" for i in range(10, 17)), "F017"}


def _facts_by_object(facts: list[dict]) -> dict[str, dict[str, list[dict]]]:
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for fact in facts:
        subject = str(fact.get("subject_id") or "")
        key = str(fact.get("key") or "")
        if subject and key:
            grouped[subject][key].append(fact)
    return grouped


def _value(facts: dict[str, list[dict]], key: str) -> str:
    rows = [row for row in facts.get(key, []) if row.get("read_status") == "available"]
    values = {str(row.get("raw_value") or "") for row in rows}
    return next(iter(values)) if len(values) == 1 else ""


def _parameter(facts: dict[str, list[dict]], occurrence: dict) -> dict | None:
    name = _value(facts, "catia_parameter_name")
    values = facts.get("catia_parameter_value_text", [])
    available = [row for row in values if row.get("read_status") == "available"]
    unique = {(str(row.get("raw_value") or ""), str(row.get("raw_unit") or "")) for row in available}
    if not name or len(unique) != 1:
        return None
    value = available[0]
    return {"name": name, "raw_value": value.get("raw_value"),
            "raw_unit": value.get("raw_unit"), "read_status": value.get("read_status"),
            "source_api": value.get("source_api"), "object_id": occurrence.get("object_id"),
            "occurrence_id": occurrence.get("occurrence_id")}


def _split_numbers(raw: str) -> tuple[list[str], list[str]]:
    if not raw:
        return [], ["number_alias_missing"]
    pieces = [piece.strip() for piece in raw.split("+")]
    diagnostics = []
    if any(not piece for piece in pieces):
        diagnostics.append("empty_number_segment")
    nonempty = [piece for piece in pieces if piece]
    if len(nonempty) != len(set(nonempty)):
        diagnostics.append("duplicate_number_segment")
    return pieces, diagnostics


def build_connection_semantics(objects: list[dict], occurrences: list[dict],
                               facts: list[dict], products: list[dict]) -> list[dict]:
    """Emit one record per native set occurrence, retaining exact hierarchy and source IDs."""
    object_ids = {str(row.get("object_id")) for row in objects if row.get("object_id")}
    properties = _facts_by_object(facts)
    products_by_id = {str(row.get("occurrence_id")): row for row in products if row.get("occurrence_id")}
    by_id = {str(row.get("occurrence_id")): row for row in occurrences if row.get("occurrence_id")}
    children: dict[str, list[str]] = defaultdict(list)
    for occurrence_id, row in by_id.items():
        children[str(row.get("parent_occurrence_id") or "")].append(occurrence_id)

    def facts_for(row: dict) -> dict[str, list[dict]]:
        return properties.get(str(row.get("object_id") or ""), {})

    def alias_for(row: dict) -> str:
        return _value(facts_for(row), "native_alias")

    def classes_for(row: dict) -> set[str]:
        return {str(item.get("raw_value")) for item in facts_for(row).get("native_object_class", [])
                if item.get("read_status") == "available"}

    def ancestors(row: dict, stop_id: str) -> list[dict]:
        chain = []
        seen = set()
        parent_id = str(row.get("parent_occurrence_id") or "")
        while parent_id and parent_id != stop_id and parent_id not in seen:
            seen.add(parent_id)
            parent = by_id.get(parent_id)
            if parent is None or parent.get("product_occurrence_id") != row.get("product_occurrence_id"):
                break
            chain.append(parent)
            parent_id = str(parent.get("parent_occurrence_id") or "")
        return chain

    result = []
    for root_id, root in by_id.items():
        alias = alias_for(root)
        if (alias not in ROOT_ALIASES or "geometrical_set" not in classes_for(root) or
            str(root.get("object_id") or "") not in object_ids):
            continue
        product_id = str(root.get("product_occurrence_id") or "")
        product = products_by_id.get(product_id, {})
        part_number = str(product.get("part_number") or "")
        role = "R" if part_number.startswith("R_") else "DM" if part_number else "unknown"
        descendants = []
        queue = deque(children.get(root_id, []))
        while queue and len(descendants) < 10000:
            occurrence_id = queue.popleft()
            row = by_id.get(occurrence_id)
            if row is None or str(row.get("product_occurrence_id") or "") != product_id:
                continue
            descendants.append(row)
            queue.extend(children.get(occurrence_id, []))
        truncated = bool(queue)
        parameters = [parameter for row in descendants
                      if (parameter := _parameter(facts_for(row), row)) is not None]
        parameter_groups = []
        for parameter in parameters:
            row = by_id[str(parameter["occurrence_id"])]
            chain = ancestors(row, root_id)
            parameter_groups.append({**parameter,
                                     "ancestor_occurrence_ids": [item["occurrence_id"] for item in chain],
                                     "ancestor_aliases": [alias_for(item) for item in chain]})
        fastener_sets = {row["occurrence_id"] for row in descendants
                          if alias_for(row) == "紧固件" and "geometrical_set" in classes_for(row)}
        points = []
        for row in descendants:
            if "point_feature" not in classes_for(row):
                continue
            chain = ancestors(row, root_id)
            parent = chain[0] if chain else {}
            parent_alias = alias_for(parent) if "geometrical_set" in classes_for(parent) else ""
            raw_number = alias_for(row)
            numbers, number_diagnostics = _split_numbers(raw_number)
            in_fastener_set = any(item["occurrence_id"] in fastener_sets for item in chain)
            components = [_value(facts_for(row), f"native_point_{axis}_m") for axis in "xyz"]
            reference_status = _value(facts_for(row), "native_point_reference_status")
            local_mm = None
            if reference_status == "absolute_part_axis" and all(components):
                try:
                    parsed = [float(component) * 1000 for component in components]
                    if all(math.isfinite(value) for value in parsed):
                        local_mm = parsed
                except ValueError:
                    pass
            points.append({"point_occurrence_id": row["occurrence_id"], "point_object_id": row.get("object_id"),
                           "parent_set_occurrence_id": parent.get("occurrence_id"),
                           "parent_set_alias": parent_alias, "raw_number_alias": raw_number,
                           "number_segments": numbers, "number_diagnostics": number_diagnostics,
                           "ancestor_occurrence_ids": [item["occurrence_id"] for item in chain],
                           "in_fastener_set": in_fastener_set,
                           "coordinate_status": "part_local_only" if local_mm is not None else
                                                "unresolved_native_point_geometry",
                           "part_local_mm": local_mm, "assembly_world_mm": None,
                           "reference_status": reference_status or "unavailable"})
        diagnostics = ["member_limit_exceeded"] if truncated else []
        if not product_id or role == "unknown":
            diagnostics.append("product_occurrence_or_part_number_unresolved")
        if ROOT_ALIASES[alias] == "fastener":
            has_parent = bool(fastener_sets)
            route = "A" if has_parent else "B"
            if not points:
                diagnostics.append("native_point_members_unavailable")
            statistics = [parameter for parameter in parameter_groups
                          if "统计信息" in parameter["ancestor_aliases"]]
            for point in points:
                first = point["parent_set_alias"][:1]
                point["customer_bucket"] = "fastener" if first and first in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" else "connector"
                if route == "A" and not point["in_fastener_set"]:
                    point["customer_bucket"] = "outside_fastener_set"
                    point["number_diagnostics"].append("outside_fastener_parent")
                if route == "B":
                    chain_aliases = [alias_for(by_id[item]) for item in point["ancestor_occurrence_ids"]]
                    expected = ("多重输出", "中心点", "紧固件编号集", "连接类型集")
                    point["path_b_chain_status"] = ("verified" if len(chain_aliases) >= 5 and
                                                     tuple(chain_aliases[1:5]) == expected else "partial")
            payload = {"path": route, "points": points, "statistics_raw": statistics,
                       "point_count": len(points),
                       "number_segment_count": sum(len(item["number_segments"]) for item in points),
                       "fastener_point_count": sum(item["customer_bucket"] == "fastener" for item in points)}
            if route == "B" and any(item["path_b_chain_status"] != "verified" for item in points):
                diagnostics.append("path_b_parent_chain_not_verified")
        else:
            relevant = [parameter for parameter in parameter_groups
                        if parameter["name"].split("_", 1)[0] in SEAL_BOND_KEYS]
            region_sets = [row for row in descendants if "geometrical_set" in classes_for(row)]
            payload = {"parameters_raw": relevant,
                       "region_member_occurrence_ids": [row["occurrence_id"] for row in region_sets],
                       "region_groups": [{"occurrence_id": row["occurrence_id"], "raw_alias": alias_for(row),
                                          "ancestor_occurrence_ids": [item["occurrence_id"] for item in ancestors(row, root_id)],
                                          "parameter_occurrence_ids": [item["occurrence_id"] for item in relevant
                                                                       if row["occurrence_id"] in item["ancestor_occurrence_ids"]]}
                                         for row in region_sets],
                       "geometry_status": "native_region_geometry_unresolved",
                       "material_association_status": "parent_reference_not_verified"}
            if not relevant:
                diagnostics.append("customer_parameters_unavailable")
        identity = "|".join((str(root.get("document_id") or ""), product_id, root_id))
        result.append({"connection_id": "CN" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24].upper(),
                       "kind": ROOT_ALIASES[alias], "raw_alias": alias,
                       "root_occurrence_id": root_id, "root_object_id": root.get("object_id"),
                       "document_id": root.get("document_id"), "product_occurrence_id": product_id,
                       "part_number": part_number, "model_role": role,
                       "customer_rule_version": RULE_VERSION,
                       "member_occurrence_ids": [row["occurrence_id"] for row in descendants],
                       "native_source_status": "partial", "geometry_link_status": "unresolved",
                       "diagnostics": diagnostics, **payload})
    return result
