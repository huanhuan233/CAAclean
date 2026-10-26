# 定义视觉提取结果与图纸事实的结构，保留原文、归一化值、坐标证据和待复核状态。
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PROMPT_VERSION = "drawing_extraction_v1"


# 接收图上可见的产品信息，并允许模型返回额外键供后续别名兼容。
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

    # 保留空值，将非字符串的可见属性转换为文本。
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

    # 仅接收字典元数据，避免模型的非对象输出进入后续处理。
    @field_validator("other_metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, value):
        return value if isinstance(value, dict) else {}


# 表示表格行标识、单元格和可选局部框，保留原始单元格值。
class TableRow(BaseModel):
    row_identifier: dict[str, Any] = Field(default_factory=dict)
    cells: dict[str, Any] = Field(default_factory=dict)
    bbox_local: list[float] | None = None

    # 把非字典的行标识或单元格容器降级为空对象。
    @field_validator("row_identifier", "cells", mode="before")
    @classmethod
    def coerce_dict(cls, value):
        return value if isinstance(value, dict) else {}


# 保存完整表格的表头层级、合并单元格、各行和单位信息。
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

    # 仅保留列表形式的表格结构，其他响应形态降级为空列表。
    @field_validator("headers", "header_hierarchy", "merged_cells", "rows", "row_identifiers", mode="before")
    @classmethod
    def coerce_list(cls, value):
        return value if isinstance(value, list) else []

    # 保证单位和运算符信息为对象，异常形态不参与后续解析。
    @field_validator("units", "operator_information", mode="before")
    @classmethod
    def coerce_table_dict(cls, value):
        return value if isinstance(value, dict) else {}


# 记录图上可见的尺寸符号、几何角色、局部证据框和模型置信度。
class SymbolDefinition(BaseModel):
    symbol: str
    visible_label: str | None = None
    visible_geometry_role: str | None = None
    annotation_text: str | None = None
    source_bbox_local: list[float] | None = None
    confidence: float | None = None


# 容纳尺寸示意图的符号定义，允许额外模型输出字段。
class SymbolDefinitionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbols: list[Any] = Field(default_factory=list)

    # 兼容符号到几何角色的字典输出，将其转换为符号记录列表。
    @field_validator("symbols", mode="before")
    @classmethod
    def coerce_symbols(cls, value):
        if isinstance(value, dict):
            return [{"symbol": key, "visible_label": key, "visible_geometry_role": item} for key, item in value.items()]
        return value if isinstance(value, list) else []


# 保留请求行、匹配行与选行证据字段；当前提取服务使用默认空结果。
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

    # 将单条字符串警告转为列表，空值转为空列表。
    @field_validator("warnings", mode="before")
    @classmethod
    def coerce_warnings(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    # 把模型返回的空布尔值按未标记处理。
    @field_validator("inferred_from_filename", "needs_review", mode="before")
    @classmethod
    def coerce_nullable_bool(cls, value):
        return False if value is None else value


# 承载可追溯图纸事实：数值、比较符、单位、来源区域和证据精度分别保存。
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

    # 数值事实必须提供数值型归一化值；该检查不执行单位换算。
    @model_validator(mode="after")
    def validate_number_value(self):
        if self.value_type == "number" and self.normalized_value is not None and not isinstance(self.normalized_value, int | float):
            raise ValueError("number facts require numeric normalized_value")
        return self


# 汇总一次提取的产品、整表、符号和事实，记录模型与提示词版本。
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


# 接收目标型号、公称尺寸和强制重提标志，由服务决定具体处理方式。
class ExtractRequest(BaseModel):
    target_code: str | None = None
    target_dn: int | None = None
    force: bool = False


# 向客户端返回提取状态及可选错误信息。
class ExtractionStatusOut(BaseModel):
    task_id: uuid.UUID
    status: str
    error_code: str | None = None
    error_message: str | None = None
