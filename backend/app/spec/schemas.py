# 定义配置映射、部件配置和规范字段目录；匹配容差与单位含义由配置和调用方约定。
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# 描述图纸符号到规范字段的映射、允许测量类型、匹配容差和复核要求。
class FieldMapping(BaseModel):
    symbol: str
    target_field: str
    confidence: float = 1.0
    needs_review: bool = False
    require_semantic_confirmation: bool = False
    measurement_types: list[str] = Field(default_factory=list)
    match_tolerance: float | None = None


# 保存部件配置版本、适用类型、字段映射及未知符号的歧义候选。
class ComponentProfile(BaseModel):
    profile_id: str
    version: str
    component_type: str
    subtype: str | None = None
    match_rules: dict[str, Any] = Field(default_factory=dict)
    field_mappings: dict[str, FieldMapping] = Field(default_factory=dict)
    ambiguity_candidates: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


# 描述规范字段语义、别名、单位、来源和默认复核要求。
class FieldDefinition(BaseModel):
    name: str
    semantic: str
    aliases: list[str] = Field(default_factory=list)
    unit: str | None = None
    source: Literal["drawing", "freecad", "manual", "profile"] = "drawing"
    applicable_types: list[str] = Field(default_factory=list)
    needs_review_default: bool = False
