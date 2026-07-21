from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CadUploadResponse(BaseModel):
    model_id: UUID
    revision_id: UUID
    status: str


class CadParseStatus(BaseModel):
    status: str
    progress: int
    status_message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class CadModelSummary(BaseModel):
    id: UUID
    name: str
    current_revision_id: UUID | None = None
    status: str | None = None
    progress: int | None = None


class CadPagedResult(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


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


class CadTreeNode(BaseModel):
    id: UUID
    parent_entity_id: UUID | None = None
    entity_type: str
    label: str
    source_ref: str | None = None
    geometry_type: str | None = None
    children: list["CadTreeNode"] = []


class CadTopologyResult(BaseModel):
    edges: list[dict[str, Any]] = []
    adjacent_faces: list[dict[str, Any]] = []
    vertices: list[dict[str, Any]] = []
    faces: list[dict[str, Any]] = []
