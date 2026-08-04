from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ParserEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    revision_id: UUID
    parent_entity_id: UUID | None = None
    entity_type: str
    source_ref: str | None = None
    source_index: int | None = None
    name: str | None = None
    label: str | None = None
    tree_path: str
    sort_order: int = 0
    geometry_type: str | None = None
    area: float | None = None
    volume: float | None = None
    length: float | None = None
    center: dict[str, Any] | list[float] | None = None
    bounding_box: dict[str, Any] | None = None
    placement: dict[str, Any] | None = None
    geometry: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str | None = None


class ParserRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    revision_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParserMesh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    revision_id: UUID
    entity_id: UUID
    mesh_type: str
    positions: list[list[float]]
    indices: list[list[int]]
    normals: list[list[float]] | None = None
    color: dict[str, Any] | list[float] | None = None
    linear_deflection: float
    angular_deflection: float | None = None
    vertex_count: int
    triangle_count: int

    @field_validator("positions")
    @classmethod
    def positions_are_xyz(cls, value: list[list[float]]) -> list[list[float]]:
        if any(len(point) != 3 for point in value):
            raise ValueError("positions must contain [x, y, z] points")
        return value

    @field_validator("indices")
    @classmethod
    def indices_are_triangles(cls, value: list[list[int]]) -> list[list[int]]:
        if any(len(face) != 3 for face in value):
            raise ValueError("indices must contain triangle index triplets")
        return value

    @field_validator("triangle_count")
    @classmethod
    def triangle_count_is_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("triangle_count must be non-negative")
        return value

    @field_validator("vertex_count")
    @classmethod
    def vertex_count_is_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("vertex_count must be non-negative")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.vertex_count != len(self.positions):
            raise ValueError("vertex_count must match positions length")
        if self.triangle_count != len(self.indices):
            raise ValueError("triangle_count must match indices length")


class ParserResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: UUID
    parser_name: str
    parser_version: str | None = None
    # 用途：记录实际几何 Kernel 及版本，避免用 FreeCAD 应用版本冒充 OCC 版本。
    kernel_name: str | None = None
    kernel_version: str | None = None
    schema_version: str
    unit: str | None = None
    bounding_box: dict[str, Any] | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    entities: list[ParserEntity]
    relations: list[ParserRelation] = Field(default_factory=list)
    meshes: list[ParserMesh] = Field(default_factory=list)
    parse_manifest: dict[str, Any] = Field(default_factory=dict)


def validate_parser_result(data: dict[str, Any]) -> ParserResult:
    return ParserResult.model_validate(data)
