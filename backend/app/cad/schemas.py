# CAD HTTP 响应模型，稳定表达实体身份、树关系、分页数量和解析状态。
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


# 上传受理结果，返回模型和版本 ID；受理不代表解析完成。
class CadUploadResponse(BaseModel):
    model_id: UUID
    revision_id: UUID
    status: str


# 面向轮询的任务进度和错误信息。
class CadParseStatus(BaseModel):
    status: str
    progress: int
    status_message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


# 列表中的模型概要及当前版本状态。
class CadModelSummary(BaseModel):
    id: UUID
    name: str
    current_revision_id: UUID | None = None
    status: str | None = None
    progress: int | None = None


# 将当前页记录与完整查询总数分开返回。
class CadPagedResult(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


# 实体详情的传输结构，保留所属版本、源身份和可选显示网格。
class CadEntityOut(BaseModel):
    id: UUID
    revision_id: UUID
    parent_entity_id: UUID | None = None
    entity_type: str
    source_ref: str | None = None
    source_index: int | None = None
    name: str | None = None
    label: str | None = None
    tree_path: str
    sort_order: int
    geometry_type: str | None = None
    area: float | None = None
    volume: float | None = None
    length: float | None = None
    center: Any = None
    bounding_box: dict[str, Any] | None = None
    placement: dict[str, Any] | None = None
    geometry: dict[str, Any]
    metadata: dict[str, Any]
    mesh: dict[str, Any] | None = None


# 树节点保留真实父子引用，children 仅表达已有结构。
class CadTreeNode(BaseModel):
    id: UUID
    parent_entity_id: UUID | None = None
    entity_type: str
    label: str
    source_ref: str | None = None
    sort_order: int | None = None
    geometry_type: str | None = None
    children: list["CadTreeNode"] = []


# 按角色分别返回面边界、邻接面、端点和关联面。
class CadTopologyResult(BaseModel):
    edges: list[dict[str, Any]] = []
    adjacent_faces: list[dict[str, Any]] = []
    vertices: list[dict[str, Any]] = []
    faces: list[dict[str, Any]] = []
