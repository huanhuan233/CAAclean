"""CAA 原生属性事实的 PostgreSQL 投影与响应组装。"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID, uuid5


_WINDOWS_PATH_RE = re.compile(r"(?i)\b[a-z]:\\[^<>:\"|?*\r\n]+")


def native_property_rows(revision_id: UUID, facts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(iter_native_property_rows(revision_id, facts))


def iter_native_property_rows(revision_id: UUID, facts: Iterable[dict[str, Any]]):
    for index, fact in enumerate(facts):
        subject_id = str(fact.get("subject_id") or "")
        if not subject_id:
            continue
        property_id = str(fact.get("property_id") or f"{subject_id}:{index}")
        payload = dict(fact)
        payload["raw_value"] = _redact_value(payload.get("raw_value"))
        payload["display_value"] = _redact_value(payload.get("display_value"))
        yield {
            "id": uuid5(revision_id, f"native-property:{property_id}:{index}"),
            "revision_id": revision_id,
            "subject_id": subject_id,
            "property_id": property_id,
            "sort_order": index,
            "payload": payload,
        }


def build_database_properties(node_id: str, node: dict[str, Any], facts: Iterable[Any]) -> dict[str, Any]:
    subject_ids = native_property_subject_ids(node_id, node)
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in facts:
        if str(row.subject_id) not in subject_ids:
            continue
        fact = dict(row.payload or {})
        key = (
            str(fact.get("tab_id") or "attributes"),
            str(fact.get("tab_label") or fact.get("tab_id") or "attributes"),
            str(fact.get("group_id") or "default"),
            str(fact.get("group_label") or fact.get("group_id") or "default"),
        )
        groups[key].append(_property_field(fact))
    return _grouped_property_response(node_id, groups)


def native_property_subject_ids(node_id: str, node: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in (
            node_id,
            node.get("occurrence_id"),
            node.get("object_id"),
            node.get("product_occurrence_id"),
            node.get("reference_id"),
            node.get("document_id"),
            node.get("referenced_document_id"),
        )
        if value
    }


def native_parameter_values(facts: Iterable[Any]) -> dict[str, str]:
    """返回树节点右侧 `= value` 所需的已入库 CATIA 参数文本。"""
    values: dict[str, str] = {}
    for row in facts:
        fact = dict(row.payload or {})
        if str(fact.get("key") or "") != "catia_parameter_value_text":
            continue
        value = fact.get("raw_display_text") or fact.get("display_value") or fact.get("raw_value")
        if value is not None and str(value) != "":
            values[str(row.subject_id)] = str(value)
    return values


def _grouped_property_response(node_id: str, groups: dict[tuple[str, str, str, str], list[dict[str, Any]]]):
    tabs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for (tab_id, tab_label, group_id, group_label), fields in groups.items():
        fields.sort(key=lambda item: (int(item.get("display_order") or 0), str(item.get("key") or "")))
        tabs[(tab_id, tab_label)].append(
            {"group_id": group_id, "group_label": group_label, "fields": fields}
        )
    result_tabs = []
    for (tab_id, tab_label), tab_groups in tabs.items():
        tab_groups.sort(key=lambda group: min((int(field.get("display_order") or 0) for field in group["fields"]), default=0))
        result_tabs.append({"tab_id": tab_id, "tab_label": tab_label, "groups": tab_groups})
    result_tabs.sort(
        key=lambda tab: min(
            (int(field.get("display_order") or 0) for group in tab["groups"] for field in group["fields"]),
            default=0,
        )
    )
    return {
        "node_id": node_id,
        "property_count": sum(len(group["fields"]) for tab in result_tabs for group in tab["groups"]),
        "tabs": result_tabs,
    }


def _property_field(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "property_id": str(fact.get("property_id") or ""),
        "key": str(fact.get("key") or ""),
        "display_name": str(fact.get("display_name") or fact.get("key") or ""),
        "raw_value": _redact_value(fact.get("raw_value")),
        "raw_unit": str(fact.get("raw_unit") or ""),
        "display_value": _redact_value(fact.get("display_value")),
        "raw_display_text": _redact_value(fact.get("raw_display_text")),
        "display_unit": str(fact.get("display_unit") or ""),
        "value_type": str(fact.get("value_type") or ""),
        "source_api": str(fact.get("source_api") or ""),
        "read_status": str(fact.get("read_status") or ""),
        "authority": str(fact.get("authority") or ""),
        "display_order": int(fact.get("display_order") or 0),
        "read_only": bool(fact.get("read_only")),
        "hidden_status": str(fact.get("hidden_status") or "unavailable"),
        "normalization_status": str(fact.get("normalization_status") or "unavailable"),
    }


def _redact_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _WINDOWS_PATH_RE.sub(lambda match: f"<local_path>\\{Path(match.group(0)).name}", value)
