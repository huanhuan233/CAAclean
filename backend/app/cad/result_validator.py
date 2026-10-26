# 入库前检查 FreeCAD JSON 结果的数据形状与网格计数；此处不做几何类别核验。
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# 实体记录契约包含自身、父实体、源引用与几何摘要，拒绝额外未知字段。
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


# 有向拓扑关系的输入契约，两个端点分别保留真实实体 ID。
class ParserRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    revision_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# 显示网格契约，坐标、三角形索引和声明计数需满足结构约束。
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

    # 每个顶点必须恰有三个坐标分量。
    @field_validator("positions")
    @classmethod
    def positions_are_xyz(cls, value: list[list[float]]) -> list[list[float]]:
        if any(len(point) != 3 for point in value):
            raise ValueError("positions must contain [x, y, z] points")
        return value

    # 每个索引记录必须恰有三个顶点索引；此处只检查三元组长度。
    @field_validator("indices")
    @classmethod
    def indices_are_triangles(cls, value: list[list[int]]) -> list[list[int]]:
        if any(len(face) != 3 for face in value):
            raise ValueError("indices must contain triangle index triplets")
        return value

    # 拒绝负三角形计数。
    @field_validator("triangle_count")
    @classmethod
    def triangle_count_is_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("triangle_count must be non-negative")
        return value

    # 拒绝负顶点计数。
    @field_validator("vertex_count")
    @classmethod
    def vertex_count_is_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("vertex_count must be non-negative")
        return value

    # 核对声明数量与实际数组长度，防止不完整网格伪装成完整输出。
    def model_post_init(self, __context: Any) -> None:
        if self.vertex_count != len(self.positions):
            raise ValueError("vertex_count must match positions length")
        if self.triangle_count != len(self.indices):
            raise ValueError("triangle_count must match indices length")


# 一次解析的完整载荷，分别记录应用与几何内核版本并附带实体、关系和显示数据。
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
    thin_wall_pairs: list[dict[str, Any]] = Field(default_factory=list)
    thin_wall_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    cylinder_end_boundaries: list[dict[str, Any]] = Field(default_factory=list)


# 将原始字典交给统一 Pydantic 契约校验，供进程入口与持久化复用。
def validate_parser_result(data: dict[str, Any]) -> ParserResult:
    return ParserResult.model_validate(data)
