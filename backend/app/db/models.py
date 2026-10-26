# 数据库持久化模型：分开保存源版本、解析几何、原生证据、测量和图纸规格结果。
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# 生成带 UTC 时区的时间，供记录创建与更新时间使用。
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# 源模型身份与当前版本指针；具体文件和解析状态归属于 Revision。
class CadModel(Base):
    __tablename__ = "cad_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    revisions: Mapped[list["CadModelRevision"]] = relationship(back_populates="model", cascade="all, delete-orphan")


# 一次源文件版本及其解析状态、摘要和产物清单，是几何和证据的共同范围。
class CadModelRevision(Base):
    __tablename__ = "cad_model_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_models.id", ondelete="CASCADE"), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_file_name: Mapped[str] = mapped_column(String, nullable=False)
    source_file_ext: Mapped[str] = mapped_column(String, nullable=False)
    source_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="uploaded")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_message: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    parser_name: Mapped[str | None] = mapped_column(String)
    parser_version: Mapped[str | None] = mapped_column(String)
    schema_version: Mapped[str | None] = mapped_column(String)
    unit: Mapped[str | None] = mapped_column(String)
    object_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    solid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    face_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vertex_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounding_box: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    parse_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    model: Mapped[CadModel] = relationship(back_populates="revisions")


# 业务零件记录，关联 CAD 版本、图纸任务和构建状态。
class ComponentBuild(Base):
    __tablename__ = "component_builds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    catalog_node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    component_id: Mapped[str] = mapped_column(String(160), nullable=False)
    component_name: Mapped[str] = mapped_column(String(255), nullable=False)
    component_type: Mapped[str] = mapped_column(String(80), nullable=False)
    component_subtype: Mapped[str | None] = mapped_column(String(80))
    family: Mapped[str | None] = mapped_column(String(160))
    standard_number: Mapped[str | None] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(80), nullable=False, default="1.0.0")
    default_dn: Mapped[int | None] = mapped_column(Integer)
    default_pn: Mapped[int | None] = mapped_column(Integer)
    cad_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_models.id", ondelete="SET NULL"))
    cad_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="SET NULL"))
    drawing_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_tasks.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(80), nullable=False, default="draft")
    status_message: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 按构建保存可编辑规格草稿，并保留对应 schema 版本。
class ComponentSpecDraft(Base):
    __tablename__ = "component_spec_drafts"

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("component_builds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.2")
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 版本内的实体身份、父子结构与几何摘要；名称和显示序号不替代实体 ID。
class CadEntity(Base):
    __tablename__ = "cad_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    parent_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_entities.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String)
    source_index: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(String)
    label: Mapped[str | None] = mapped_column(String)
    tree_path: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    geometry_type: Mapped[str | None] = mapped_column(String)
    area: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    length: Mapped[float | None] = mapped_column(Float)
    center: Mapped[dict | list | None] = mapped_column(JSONB)
    bounding_box: Mapped[dict | None] = mapped_column(JSONB)
    placement: Mapped[dict | None] = mapped_column(JSONB)
    geometry: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    fingerprint: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 原生属性事实按 subject_id 归属对象，payload 保留字段来源与读取结果。
class CadNativePropertyFact(Base):
    __tablename__ = "cad_native_property_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(String, nullable=False)
    property_id: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CadNativeEvidence(Base):
    """经 Worker 校验并入库的原生语义记录；按类型及原始顺序分页读取。"""

    __tablename__ = "cad_native_evidence"

    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(64), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


# 保存两个实体间的有向关系，关系类别定义边的工程含义。
class CadRelation(Base):
    __tablename__ = "cad_relations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_entities.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 保存显示用离散网格及离散精度，不作为精确 B-Rep 测量值的替代。
class CadMesh(Base):
    __tablename__ = "cad_meshes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_entities.id", ondelete="CASCADE"), nullable=False)
    mesh_type: Mapped[str] = mapped_column(String, nullable=False)
    positions: Mapped[list] = mapped_column(JSONB, nullable=False)
    indices: Mapped[list] = mapped_column(JSONB, nullable=False)
    normals: Mapped[list | None] = mapped_column(JSONB)
    color: Mapped[dict | list | None] = mapped_column(JSONB)
    linear_deflection: Mapped[float] = mapped_column(Float, nullable=False)
    angular_deflection: Mapped[float | None] = mapped_column(Float)
    vertex_count: Mapped[int] = mapped_column(Integer, nullable=False)
    triangle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 保存特征候选、参与实体和算法版本；候选状态与置信度分别保留。
class CadFeatureCandidate(Base):
    __tablename__ = "cad_feature_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    scope_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_entities.id", ondelete="CASCADE"), nullable=False)
    feature_type: Mapped[str] = mapped_column(String, nullable=False)
    source_entity_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    axis: Mapped[list | dict | None] = mapped_column(JSONB)
    center: Mapped[list | dict | None] = mapped_column(JSONB)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    algorithm: Mapped[str] = mapped_column(String, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 记录原始值、规范化值、单位和方法，可关联候选特征而不覆盖其设计参数。
class CadMeasurement(Base):
    __tablename__ = "cad_measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    scope_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_entities.id", ondelete="CASCADE"), nullable=False)
    feature_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cad_feature_candidates.id", ondelete="SET NULL")
    )
    measurement_type: Mapped[str] = mapped_column(String, nullable=False)
    raw_value: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    normalized_value: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    unit: Mapped[str | None] = mapped_column(String)
    source_entity_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    method: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    algorithm_version: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 图纸与几何融合任务的状态、提取结果及校验报告。
class CadSpecTask(Base):
    __tablename__ = "cad_spec_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_message: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(String)
    vision_model: Mapped[str | None] = mapped_column(String)
    selected_component_code: Mapped[str | None] = mapped_column(String)
    selected_specification: Mapped[str | None] = mapped_column(String)
    drawing_extraction: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    freecad_facts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    semantic_result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    validation_report: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# 记录任务输入文件、校验和与来源元数据，用于追溯证据。
class CadSpecSource(Base):
    __tablename__ = "cad_spec_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_tasks.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    template_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 保存原图区域、裁剪范围和提供方原始结果，支持区域级提取定位。
class CadDrawingRegion(Base):
    __tablename__ = "cad_drawing_regions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_tasks.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_sources.id", ondelete="CASCADE"), nullable=False)
    parent_region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_drawing_regions.id", ondelete="SET NULL"))
    region_type: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_region_type: Mapped[str | None] = mapped_column(String)
    bbox_normalized: Mapped[list] = mapped_column(JSONB, nullable=False)
    bbox_pixels: Mapped[list] = mapped_column(JSONB, nullable=False)
    padded_bbox_pixels: Mapped[list] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crop_file_path: Mapped[str | None] = mapped_column(Text)
    crop_file_name: Mapped[str | None] = mapped_column(String)
    crop_sha256: Mapped[str | None] = mapped_column(String(64))
    crop_width: Mapped[int | None] = mapped_column(Integer)
    crop_height: Mapped[int | None] = mapped_column(Integer)
    raw_provider_result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 图纸提取事实保留原值、规范值、定位精度及复核状态，按生成轮次追踪。
class CadDrawingFact(Base):
    __tablename__ = "cad_drawing_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_tasks.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_sources.id", ondelete="CASCADE"), nullable=False)
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_drawing_regions.id", ondelete="SET NULL"))
    fact_key: Mapped[str] = mapped_column(String, nullable=False)
    fact_type: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String)
    label: Mapped[str | None] = mapped_column(String)
    operator: Mapped[str] = mapped_column(String, nullable=False)
    raw_value: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    normalized_value: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    value_type: Mapped[str | None] = mapped_column(String)
    unit: Mapped[str | None] = mapped_column(String)
    source_bbox_original: Mapped[list | None] = mapped_column(JSONB)
    source_bbox_normalized: Mapped[list | None] = mapped_column(JSONB)
    source_bbox_precision: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(default=False, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    generation_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default="current")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 将图纸值、实测值和最终采用值分开，映射成功不自动等于尺寸符合要求。
class CadSpecField(Base):
    __tablename__ = "cad_spec_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_tasks.id", ondelete="CASCADE"), nullable=False)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    profile_id: Mapped[str | None] = mapped_column(String)
    profile_version: Mapped[str | None] = mapped_column(String)
    symbol: Mapped[str | None] = mapped_column(String)
    drawing_value: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    measured_value: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    normalized_measured_value: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    resolved_value: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String)
    drawing_fact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_drawing_facts.id", ondelete="SET NULL"))
    measurement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_measurements.id", ondelete="SET NULL"))
    feature_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_feature_candidates.id", ondelete="SET NULL"))
    source_entity_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    mapping_status: Mapped[str] = mapped_column(String, nullable=False)
    geometry_match_status: Mapped[str] = mapped_column(String, nullable=False)
    conformance_status: Mapped[str] = mapped_column(String, nullable=False)
    review_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    drawing_value_confidence: Mapped[float | None] = mapped_column(Float)
    measurement_confidence: Mapped[float | None] = mapped_column(Float)
    mapping_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="current")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 关联规格字段与图纸、测量或实体证据，保留每条证据的值和置信度。
class CadSpecFieldEvidence(Base):
    __tablename__ = "cad_spec_field_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_fields.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_spec_tasks.id", ondelete="CASCADE"), nullable=False)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    drawing_fact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_drawing_facts.id", ondelete="SET NULL"))
    measurement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_measurements.id", ondelete="SET NULL"))
    feature_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_feature_candidates.id", ondelete="SET NULL"))
    source_entity_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


Index("ix_cad_model_revisions_model_id", CadModelRevision.model_id)
Index("ix_cad_model_revisions_status", CadModelRevision.status)
Index("ix_component_builds_component_id", ComponentBuild.component_id)
Index("ix_component_builds_cad_revision_id", ComponentBuild.cad_revision_id)
Index("ix_component_builds_drawing_task_id", ComponentBuild.drawing_task_id)
Index("ix_component_builds_status", ComponentBuild.status)
Index("ix_cad_entities_revision_id", CadEntity.revision_id)
Index("ix_cad_entities_parent_entity_id", CadEntity.parent_entity_id)
Index("ix_cad_entities_revision_type", CadEntity.revision_id, CadEntity.entity_type)
Index("ix_cad_native_property_revision", CadNativePropertyFact.revision_id)
Index("ix_cad_native_property_subject", CadNativePropertyFact.revision_id, CadNativePropertyFact.subject_id)
Index("ix_cad_relations_revision_id", CadRelation.revision_id)
Index("ix_cad_relations_source_entity_id", CadRelation.source_entity_id)
Index("ix_cad_relations_target_entity_id", CadRelation.target_entity_id)
Index("ix_cad_relations_revision_type", CadRelation.revision_id, CadRelation.relation_type)
Index("ix_cad_meshes_revision_id", CadMesh.revision_id)
Index("ix_cad_meshes_entity_id", CadMesh.entity_id)
Index("ix_cad_feature_candidates_revision_id", CadFeatureCandidate.revision_id)
Index("ix_cad_feature_candidates_scope_entity_id", CadFeatureCandidate.scope_entity_id)
Index("ix_cad_feature_candidates_revision_version", CadFeatureCandidate.revision_id, CadFeatureCandidate.algorithm_version)
Index("ix_cad_measurements_revision_id", CadMeasurement.revision_id)
Index("ix_cad_measurements_scope_entity_id", CadMeasurement.scope_entity_id)
Index("ix_cad_measurements_feature_id", CadMeasurement.feature_id)
Index("ix_cad_measurements_revision_version", CadMeasurement.revision_id, CadMeasurement.algorithm_version)
Index("ix_cad_spec_tasks_revision_id", CadSpecTask.revision_id)
Index("ix_cad_spec_sources_task_id", CadSpecSource.task_id)
Index("ix_cad_drawing_regions_task_id", CadDrawingRegion.task_id)
Index("ix_cad_drawing_regions_source_id", CadDrawingRegion.source_id)
Index("ix_cad_drawing_regions_active", CadDrawingRegion.task_id, CadDrawingRegion.status)
Index("ix_cad_drawing_facts_task_id", CadDrawingFact.task_id)
Index("ix_cad_drawing_facts_current", CadDrawingFact.task_id, CadDrawingFact.status)
Index("ix_cad_drawing_facts_task_key", CadDrawingFact.task_id, CadDrawingFact.fact_key)
Index("ix_cad_spec_fields_task_id", CadSpecField.task_id)
Index("ix_cad_spec_fields_task_name", CadSpecField.task_id, CadSpecField.field_name)
Index("ix_cad_spec_fields_current", CadSpecField.task_id, CadSpecField.status)
Index("ix_cad_spec_field_evidence_field_id", CadSpecFieldEvidence.field_id)
Index("ix_cad_spec_field_evidence_task_id", CadSpecFieldEvidence.task_id)
