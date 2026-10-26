# 按配置规则把图纸尺寸事实映射为部件规格参数，保留图纸来源和未确认字段。
from __future__ import annotations

from typing import Any, Literal

from app.spec.registry import ProfileRegistry
from app.spec.schemas import ComponentProfile, FieldMapping
from app.spec.templates import sanitize_template_structure


# 选择部件配置，生成参数并应用模板结构，同时记录配置版本和规则算法来源。
def build_component_spec(
    facts: list[dict[str, Any] | Any],
    *,
    component_type: str | None,
    subtype: str | None,
    profile_id: str | None = None,
    template: dict[str, Any] | None = None,
    template_mode: Literal["skeleton", "field-template"] = "skeleton",
    registry: ProfileRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or ProfileRegistry.default()
    profile = registry.select(component_type=component_type, subtype=subtype, profile_id=profile_id)
    fact_items = [_fact_dict(fact) for fact in facts]
    generated = _build_parameters_from_facts(fact_items, profile)
    parameters = _apply_template(generated, template=template, template_mode=template_mode)
    return {
        "schema_version": "component_spec_v1",
        "template_mode": template_mode,
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "component_type": component_type or "unknown",
        "subtype": subtype,
        "parameters": parameters,
        "metadata": {
            "mapping_algorithm": "phase6.rule_registry",
            "ai_used": False,
        },
    }


# 只处理具有符号的尺寸事实，已知符号用配置映射，其余保留通用参数。
def _build_parameters_from_facts(facts: list[dict[str, Any]], profile: ComponentProfile) -> list[dict[str, Any]]:
    parameters = []
    for fact in facts:
        if fact.get("fact_type") != "dimension":
            continue
        symbol = str(fact.get("symbol") or "").strip()
        if not symbol:
            continue
        mapping = profile.field_mappings.get(symbol)
        if mapping:
            parameters.append(_mapped_parameter(fact, mapping))
            continue
        parameters.append(_generic_parameter(fact, ambiguity_candidates=profile.ambiguity_candidates.get(symbol, [])))
    return parameters


# 生成配置定义的字段名，保留图纸值与证据，按配置决定语义复核标记。
def _mapped_parameter(fact: dict[str, Any], mapping: FieldMapping) -> dict[str, Any]:
    return {
        "name": mapping.target_field,
        "symbol": mapping.symbol,
        "raw_value": fact.get("raw_value"),
        "normalized_value": fact.get("normalized_value"),
        "unit": fact.get("unit"),
        "operator": fact.get("operator") or "eq",
        "source_fact_key": fact.get("fact_key"),
        "source_region_id": fact.get("source_region_id"),
        "source_bbox_original": fact.get("source_bbox_original"),
        "source_bbox_precision": fact.get("source_bbox_precision"),
        "confidence": min(float(fact.get("confidence") or 1), mapping.confidence),
        "needs_review": bool(mapping.needs_review or mapping.require_semantic_confirmation),
        "metadata": {
            "mapping_source": "profile",
            "require_semantic_confirmation": mapping.require_semantic_confirmation,
        },
    }


# 保留未知符号的原始事实并附加歧义候选，始终标记待复核。
def _generic_parameter(fact: dict[str, Any], *, ambiguity_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    symbol = str(fact.get("symbol") or "unknown").strip() or "unknown"
    return {
        "name": f"drawing_parameter_{symbol}",
        "symbol": symbol,
        "raw_value": fact.get("raw_value"),
        "normalized_value": fact.get("normalized_value"),
        "unit": fact.get("unit"),
        "operator": fact.get("operator") or "unknown",
        "source_fact_key": fact.get("fact_key"),
        "source_region_id": fact.get("source_region_id"),
        "source_bbox_original": fact.get("source_bbox_original"),
        "source_bbox_precision": fact.get("source_bbox_precision"),
        "confidence": fact.get("confidence"),
        "needs_review": True,
        "metadata": {
            "mapping_source": "generic",
            "ambiguity_candidates": ambiguity_candidates,
        },
    }


# 骨架模式直接返回生成参数；字段模板仅按模板名称和顺序选取参数，空缺标待复核。
def _apply_template(parameters: list[dict[str, Any]], *, template: dict[str, Any] | None, template_mode: str) -> list[dict[str, Any]]:
    if template_mode == "skeleton" or not template:
        return parameters
    # 只读取模板字段结构，模板预填值不会覆盖本次图纸事实。
    structure = sanitize_template_structure(template, mode="structure_only")
    by_name = {parameter["name"]: parameter for parameter in parameters}
    result = []
    for item in structure.get("parameters", []):
        name = item.get("name")
        if not name:
            continue
        result.append(by_name.get(name, {"name": name, "needs_review": True, "metadata": {"mapping_source": "template_unfilled"}}))
    return result


# 将字典或模型转为事实字典；普通对象只抽取此处列出的尺寸属性。
def _fact_dict(fact) -> dict[str, Any]:
    if isinstance(fact, dict):
        return fact
    if hasattr(fact, "model_dump"):
        return fact.model_dump(mode="json")
    return {
        key: getattr(fact, key)
        for key in dir(fact)
        if not key.startswith("_") and key in {"fact_key", "fact_type", "symbol", "raw_value", "normalized_value", "unit", "operator"}
    }

