from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CadModel(Base):
    __tablename__ = "cad_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    revisions: Mapped[list["CadModelRevision"]] = relationship(back_populates="model", cascade="all, delete-orphan")


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


class CadRelation(Base):
    __tablename__ = "cad_relations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_model_revisions.id", ondelete="CASCADE"), nullable=False)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cad_entities.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


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


Index("ix_cad_model_revisions_model_id", CadModelRevision.model_id)
Index("ix_cad_model_revisions_status", CadModelRevision.status)
Index("ix_cad_entities_revision_id", CadEntity.revision_id)
Index("ix_cad_entities_parent_entity_id", CadEntity.parent_entity_id)
Index("ix_cad_entities_revision_type", CadEntity.revision_id, CadEntity.entity_type)
Index("ix_cad_relations_revision_id", CadRelation.revision_id)
Index("ix_cad_relations_source_entity_id", CadRelation.source_entity_id)
Index("ix_cad_relations_target_entity_id", CadRelation.target_entity_id)
Index("ix_cad_relations_revision_type", CadRelation.revision_id, CadRelation.relation_type)
Index("ix_cad_meshes_revision_id", CadMesh.revision_id)
Index("ix_cad_meshes_entity_id", CadMesh.entity_id)
