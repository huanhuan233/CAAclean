from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldMapping(BaseModel):
    symbol: str
    target_field: str
    confidence: float = 1.0
    needs_review: bool = False
    require_semantic_confirmation: bool = False


class ComponentProfile(BaseModel):
    profile_id: str
    version: str
    component_type: str
    subtype: str | None = None
    match_rules: dict[str, Any] = Field(default_factory=dict)
    field_mappings: dict[str, FieldMapping] = Field(default_factory=dict)
    ambiguity_candidates: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class FieldDefinition(BaseModel):
    name: str
    semantic: str
    aliases: list[str] = Field(default_factory=list)
    unit: str | None = None
    source: Literal["drawing", "freecad", "manual", "profile"] = "drawing"
    applicable_types: list[str] = Field(default_factory=list)
    needs_review_default: bool = False

