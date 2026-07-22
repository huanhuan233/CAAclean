from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PROMPT_VERSION = "drawing_extraction_v1"


class ProductInfoResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    component_code: str | None = None
    component_name_raw: str | None = None
    component_type_raw: str | None = None
    subtype_raw: str | None = None
    facing_type: str | None = None
    material: str | None = None
    pressure_class: str | None = None
    standard_number: str | None = None
    standard_title: str | None = None
    series: str | None = None
    other_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "component_code",
        "component_name_raw",
        "component_type_raw",
        "subtype_raw",
        "facing_type",
        "material",
        "pressure_class",
        "standard_number",
        "standard_title",
        "series",
        mode="before",
    )
    @classmethod
    def coerce_visible_text(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    @field_validator("other_metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, value):
        return value if isinstance(value, dict) else {}


class TableRow(BaseModel):
    row_identifier: dict[str, Any] = Field(default_factory=dict)
    cells: dict[str, Any] = Field(default_factory=dict)
    bbox_local: list[float] | None = None

    @field_validator("row_identifier", "cells", mode="before")
    @classmethod
    def coerce_dict(cls, value):
        return value if isinstance(value, dict) else {}


class TableExtractionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    headers: list[Any] = Field(default_factory=list)
    header_hierarchy: list[Any] = Field(default_factory=list)
    merged_cells: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[Any] = Field(default_factory=list)
    row_identifiers: list[Any] = Field(default_factory=list)
    units: dict[str, Any] = Field(default_factory=dict)
    operator_information: dict[str, Any] = Field(default_factory=dict)

    @field_validator("headers", "header_hierarchy", "merged_cells", "rows", "row_identifiers", mode="before")
    @classmethod
    def coerce_list(cls, value):
        return value if isinstance(value, list) else []

    @field_validator("units", "operator_information", mode="before")
    @classmethod
    def coerce_table_dict(cls, value):
        return value if isinstance(value, dict) else {}


class SymbolDefinition(BaseModel):
    symbol: str
    visible_label: str | None = None
    visible_geometry_role: str | None = None
    annotation_text: str | None = None
    source_bbox_local: list[float] | None = None
    confidence: float | None = None


class SymbolDefinitionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbols: list[Any] = Field(default_factory=list)

    @field_validator("symbols", mode="before")
    @classmethod
    def coerce_symbols(cls, value):
        if isinstance(value, dict):
            return [{"symbol": key, "visible_label": key, "visible_geometry_role": item} for key, item in value.items()]
        return value if isinstance(value, list) else []


class TargetRowResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    requested_code: str | None = None
    requested_dn: int | None = None
    matched_code: str | None = None
    matched_dn: int | None = None
    selected_row: Any = Field(default_factory=dict)
    row_bbox_local: list[float] | None = None
    selection_confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    inferred_from_filename: bool = False
    needs_review: bool = False

    @field_validator("warnings", mode="before")
    @classmethod
    def coerce_warnings(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("inferred_from_filename", "needs_review", mode="before")
    @classmethod
    def coerce_nullable_bool(cls, value):
        return False if value is None else value


class DrawingFact(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: uuid.UUID | None = None
    fact_key: str
    fact_type: str
    symbol: str | None = None
    label: str | None = None
    operator: Literal["eq", "gte", "lte", "approx", "between", "categorical", "unknown"]
    raw_value: Any = None
    normalized_value: Any = None
    value_type: str | None = None
    unit: str | None = None
    source_region_id: uuid.UUID | None = None
    source_bbox_original: list[int] | None = None
    source_bbox_normalized: list[float] | None = None
    source_bbox_precision: Literal["cell", "row", "region"] | None = None
    confidence: float | None = None
    needs_review: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_number_value(self):
        if self.value_type == "number" and self.normalized_value is not None and not isinstance(self.normalized_value, int | float):
            raise ValueError("number facts require numeric normalized_value")
        return self


class DrawingExtractionResult(BaseModel):
    task_id: uuid.UUID
    source_id: uuid.UUID
    product_info: ProductInfoResult
    table: TableExtractionResult
    symbols: SymbolDefinitionResult
    target_row: TargetRowResult
    facts: list[DrawingFact]
    model_name: str
    prompt_version: str = PROMPT_VERSION
    warnings: list[str] = Field(default_factory=list)


class ExtractRequest(BaseModel):
    target_code: str | None = None
    target_dn: int | None = None
    force: bool = False


class ExtractionStatusOut(BaseModel):
    task_id: uuid.UUID
    status: str
    error_code: str | None = None
    error_message: str | None = None
