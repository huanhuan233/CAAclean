# 约束构建、重试、规范草稿和融合请求的输入结构；融合默认采用补空模式。
from typing import Literal

from pydantic import BaseModel, Field


# 定义目录选择、构件名称、标准编号及业务版本的创建字段约束。
class ComponentBuildCreateFields(BaseModel):
    category_code: str = Field(min_length=1, max_length=80)
    part_type_code: str = Field(min_length=1, max_length=80)
    component_name: str = Field(min_length=1, max_length=255)
    standard_number: str | None = None
    version: str = "1.0.0"


# 把重试对象限制为模型来源或图纸来源，禁止任意后台任务角色。
class ComponentBuildRetryIn(BaseModel):
    role: Literal["reference_step", "drawing"]


# 同时接收结构化规范、可选原始 YAML 和来源文件名，供一致性校验后保存。
class ComponentSpecDraftIn(BaseModel):
    data: dict
    yaml: str | None = None
    source_filename: str | None = None


# 控制是否覆盖已有规范字段，默认 False 保留用户已填内容。
class ComponentBuildFusionIn(BaseModel):
    overwrite: bool = False
