# 将图纸符号通过部件配置绑定到规格字段，并匹配几何测量；匹配状态与合规状态分别保存。
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from app.spec.registry import ProfileRegistry
from app.spec.schemas import FieldMapping


MappingStatus = Literal["matched", "ambiguous", "unmatched"]
GeometryMatchStatus = Literal["within_match_tolerance", "outside_match_tolerance", "not_measurable"]
ConformanceStatus = Literal["pass", "fail", "unknown", "not_applicable"]
ReviewStatus = Literal["pending", "needs_review", "confirmed", "rejected"]


# 同时保存图纸值、测量值、解析值、证据引用和四类状态，供持久化及人工复核。
@dataclass
class SpecFieldBinding:
    task_id: uuid.UUID
    revision_id: uuid.UUID
    field_name: str
    profile_id: str
    profile_version: str
    symbol: str | None
    drawing_value: Any
    measured_value: Any
    normalized_measured_value: Any
    resolved_value: Any
    unit: str | None
    drawing_fact_id: uuid.UUID | None
    measurement_id: uuid.UUID | None
    feature_id: uuid.UUID | None
    source_entity_ids: list[str]
    mapping_status: MappingStatus
    geometry_match_status: GeometryMatchStatus
    conformance_status: ConformanceStatus
    review_status: ReviewStatus
    drawing_value_confidence: float | None
    measurement_confidence: float | None
    mapping_confidence: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: uuid.UUID | None = None


# 按选定配置逐符号建立绑定，同符号多事实标记歧义，未映射尺寸仍保留为通用字段。
def bind_spec_fields(
    *,
    task_id: uuid.UUID,
    revision_id: uuid.UUID,
    drawing_facts: list[dict[str, Any] | Any],
    measurements: list[dict[str, Any] | Any],
    component_type: str | None,
    subtype: str | None,
    profile_id: str | None = None,
    registry: ProfileRegistry | None = None,
) -> list[SpecFieldBinding]:
    registry = registry or ProfileRegistry.default()
    profile = registry.select(component_type=component_type, subtype=subtype, profile_id=profile_id)
    facts = [_as_dict(fact) for fact in drawing_facts]
    measurement_items = [_as_dict(measurement) for measurement in measurements]
    by_symbol = _group_by_symbol(facts)

    bindings: list[SpecFieldBinding] = []
    consumed_fact_ids: set[str] = set()
    for symbol, mapping in profile.field_mappings.items():
        matches = by_symbol.get(symbol, [])
        if not matches:
            continue
        consumed_fact_ids.update(str(_id(match)) for match in matches if _id(match))
        # 同符号多个事实时只以首条构建当前绑定，同时显式标 ambiguous；应先按目标行筛选。
        fact = matches[0]
        mapping_status: MappingStatus = "ambiguous" if len(matches) > 1 else "matched"
        bindings.append(
            _binding_for_mapping(
                task_id=task_id,
                revision_id=revision_id,
                profile_id=profile.profile_id,
                profile_version=profile.version,
                fact=fact,
                mapping=mapping,
                measurements=measurement_items,
                mapping_status=mapping_status,
            )
        )

    for fact in facts:
        fact_id = _id(fact)
        if fact_id and str(fact_id) in consumed_fact_ids:
            continue
        if fact.get("fact_type") != "dimension":
            continue
        bindings.append(_unmatched_binding(task_id, revision_id, profile.profile_id, profile.version, fact))

    return bindings


# 选择候选测量并记录几何匹配程度；解析值仍取图纸事实，合规结论保持 unknown。
def _binding_for_mapping(
    *,
    task_id: uuid.UUID,
    revision_id: uuid.UUID,
    profile_id: str,
    profile_version: str,
    fact: dict[str, Any],
    mapping: FieldMapping,
    measurements: list[dict[str, Any]],
    mapping_status: MappingStatus,
) -> SpecFieldBinding:
    measurement = _best_measurement(fact, mapping, measurements)
    drawing_value = fact.get("normalized_value")
    measured_value = _measurement_value(measurement) if measurement else None
    geometry_status = _geometry_status(fact, measurement, mapping)
    source_entity_ids = [str(value) for value in (measurement.get("source_entity_ids", []) if measurement else [])]
    measurement_confidence = float(measurement.get("confidence")) if measurement and measurement.get("confidence") is not None else None
    review_status: ReviewStatus = "needs_review" if mapping_status == "ambiguous" or mapping.needs_review else "pending"
    reason = _reason(mapping_status, measurement, geometry_status)
    return SpecFieldBinding(
        task_id=task_id,
        revision_id=revision_id,
        field_name=mapping.target_field,
        profile_id=profile_id,
        profile_version=profile_version,
        symbol=mapping.symbol,
        drawing_value=drawing_value,
        measured_value=measured_value,
        # 这里直接复用测量归一化值，不另做单位换算；调用方需保证与图纸值单位一致。
        normalized_measured_value=measured_value,
        resolved_value=drawing_value,
        unit=fact.get("unit") or (measurement.get("unit") if measurement else None),
        drawing_fact_id=_id(fact),
        measurement_id=_id(measurement) if measurement else None,
        feature_id=_feature_id(measurement) if measurement else None,
        source_entity_ids=source_entity_ids,
        mapping_status=mapping_status,
        geometry_match_status=geometry_status,
        conformance_status="unknown",
        review_status=review_status,
        drawing_value_confidence=float(fact.get("confidence")) if fact.get("confidence") is not None else None,
        measurement_confidence=measurement_confidence,
        mapping_confidence=_mapping_confidence(fact, measurement, mapping, mapping_status, geometry_status),
        reason=reason,
        metadata={
            "operator": fact.get("operator") or "eq",
            "measurement_type": measurement.get("measurement_type") if measurement else None,
            "match_tolerance": mapping.match_tolerance,
            "resolved_value_source": "drawing_fact",
        },
    )


# 为没有配置映射的尺寸创建待复核通用字段，明确无可用测量及合规结论。
def _unmatched_binding(task_id, revision_id, profile_id: str, profile_version: str, fact: dict[str, Any]) -> SpecFieldBinding:
    symbol = str(fact.get("symbol") or "unknown").strip() or "unknown"
    return SpecFieldBinding(
        task_id=task_id,
        revision_id=revision_id,
        field_name=f"drawing_parameter_{symbol}",
        profile_id=profile_id,
        profile_version=profile_version,
        symbol=symbol,
        drawing_value=fact.get("normalized_value"),
        measured_value=None,
        normalized_measured_value=None,
        resolved_value=fact.get("normalized_value"),
        unit=fact.get("unit"),
        drawing_fact_id=_id(fact),
        measurement_id=None,
        feature_id=None,
        source_entity_ids=[],
        mapping_status="unmatched",
        geometry_match_status="not_measurable",
        conformance_status="unknown",
        review_status="needs_review",
        drawing_value_confidence=float(fact.get("confidence")) if fact.get("confidence") is not None else None,
        measurement_confidence=None,
        mapping_confidence=0.35,
        reason="no_profile_mapping_for_symbol",
        metadata={"operator": fact.get("operator") or "eq", "resolved_value_source": "drawing_fact"},
    )


# 只考虑配置允许的测量类型，优先数值距离最小者，再按置信度降序打破平局。
def _best_measurement(fact: dict[str, Any], mapping: FieldMapping, measurements: list[dict[str, Any]]) -> dict[str, Any] | None:
    allowed_types = set(mapping.measurement_types)
    if not allowed_types:
        return None
    candidates = [measurement for measurement in measurements if measurement.get("measurement_type") in allowed_types]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (_numeric_distance(fact.get("normalized_value"), _measurement_value(item)), -float(item.get("confidence") or 0)))[0]


# 在匹配容差下比较图纸与测量值，支持等值、上下界和近似，区间值暂不可测。
def _geometry_status(fact: dict[str, Any], measurement: dict[str, Any] | None, mapping: FieldMapping) -> GeometryMatchStatus:
    if measurement is None:
        return "not_measurable"
    operator = fact.get("operator") or "eq"
    drawing_value = fact.get("normalized_value")
    measured_value = _measurement_value(measurement)
    # 此容差用于几何候选匹配，数值单位随输入；它不是独立的产品合规公差。
    tolerance = mapping.match_tolerance if mapping.match_tolerance is not None else 0.1
    if not isinstance(drawing_value, int | float) or not isinstance(measured_value, int | float):
        return "not_measurable"
    if operator == "gte":
        return "within_match_tolerance" if measured_value + tolerance >= drawing_value else "outside_match_tolerance"
    if operator == "lte":
        return "within_match_tolerance" if measured_value - tolerance <= drawing_value else "outside_match_tolerance"
    # 近似比较允许至少 2% 的图纸值偏差，并与配置的绝对容差取较大者。
    if operator == "approx":
        return "within_match_tolerance" if abs(measured_value - drawing_value) <= max(tolerance, abs(drawing_value) * 0.02) else "outside_match_tolerance"
    if operator == "between":
        return "not_measurable"
    return "within_match_tolerance" if abs(measured_value - drawing_value) <= tolerance else "outside_match_tolerance"


# 按符号、单位、数值、配置及几何证据累加启发式分数，并对歧义扣分。
def _mapping_confidence(fact: dict[str, Any], measurement: dict[str, Any] | None, mapping: FieldMapping, mapping_status: str, geometry_status: str) -> float:
    score = 0.35
    if fact.get("symbol") == mapping.symbol:
        score += 0.25
    if fact.get("unit"):
        score += 0.08
    if isinstance(fact.get("normalized_value"), int | float):
        score += 0.07
    score += min(mapping.confidence, 1.0) * 0.15
    if measurement is not None:
        score += 0.08
    if geometry_status == "within_match_tolerance":
        score += 0.07
    if mapping_status == "ambiguous":
        score -= 0.2
    return max(0.0, min(1.0, round(score, 4)))


# 根据候选测量是否存在、符号歧义和几何状态生成可解释原因码。
def _reason(mapping_status: str, measurement: dict[str, Any] | None, geometry_status: str) -> str:
    if measurement is None:
        return "profile_symbol_matched_no_measurement_type_match"
    if mapping_status == "ambiguous":
        return f"profile_symbol_ambiguous_geometry_{geometry_status}"
    return f"profile_symbol_and_measurement_type_matched_geometry_{geometry_status}"


# 去除符号首尾空白后分组，保留同符号的全部事实供歧义判断。
def _group_by_symbol(facts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        symbol = str(fact.get("symbol") or "").strip()
        if symbol:
            grouped.setdefault(symbol, []).append(fact)
    return grouped


# 读取测量归一化值，兼容直接标量及含 value 键的对象。
def _measurement_value(measurement: dict[str, Any] | None):
    if not measurement:
        return None
    value = measurement.get("normalized_value")
    if isinstance(value, dict):
        return value.get("value")
    return value


# 两个值都为数值时计算绝对差，否则返回无穷大以降低候选优先级。
def _numeric_distance(left, right) -> float:
    if isinstance(left, int | float) and isinstance(right, int | float):
        return abs(left - right)
    return float("inf")


# 读取对象主键并转为 UUID，缺失时返回空值。
def _id(item: dict[str, Any] | None) -> uuid.UUID | None:
    if not item or item.get("id") is None:
        return None
    return uuid.UUID(str(item["id"]))


# 读取测量关联特征 UUID，缺失时返回空值。
def _feature_id(item: dict[str, Any] | None) -> uuid.UUID | None:
    if not item or item.get("feature_id") is None:
        return None
    return uuid.UUID(str(item["feature_id"]))


# 兼容字典、Pydantic 模型和 ORM 对象，只抽取绑定所需属性。
def _as_dict(item) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    keys = {
        "id",
        "fact_key",
        "fact_type",
        "symbol",
        "label",
        "operator",
        "raw_value",
        "normalized_value",
        "unit",
        "confidence",
        "measurement_type",
        "feature_id",
        "source_entity_ids",
    }
    return {key: getattr(item, key) for key in keys if hasattr(item, key)}

