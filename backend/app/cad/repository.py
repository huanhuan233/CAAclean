from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadEntity, CadMesh, CadModel, CadModelRevision, CadRelation, ComponentBuild


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class CadRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_upload_revision(
        self,
        *,
        name: str,
        source_file_name: str,
        source_file_ext: str,
        source_file_path: str,
        source_file_size: int,
        source_sha256: str,
    ) -> tuple[CadModel, CadModelRevision]:
        model = CadModel(name=name)
        self.session.add(model)
        await self.session.flush()
        revision = CadModelRevision(
            model_id=model.id,
            revision_no=1,
            source_file_name=source_file_name,
            source_file_ext=source_file_ext,
            source_file_path=source_file_path,
            source_file_size=source_file_size,
            source_sha256=source_sha256,
            status="queued",
            progress=0,
            status_message="queued",
        )
        self.session.add(revision)
        await self.session.flush()
        model.current_revision_id = revision.id
        await self.session.commit()
        await self.session.refresh(model)
        await self.session.refresh(revision)
        return model, revision

    async def get_revision(self, revision_id: uuid.UUID) -> CadModelRevision | None:
        return await self.session.get(CadModelRevision, revision_id)

    async def get_entity(self, entity_id: uuid.UUID) -> CadEntity | None:
        return await self.session.get(CadEntity, entity_id)

    async def set_revision_status(
        self,
        revision_id: uuid.UUID,
        *,
        status: str,
        progress: int,
        status_message: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        revision = await self.get_revision(revision_id)
        if revision is None:
            return
        revision.status = status
        revision.progress = progress
        revision.status_message = status_message
        revision.error_code = error_code
        revision.error_message = error_message
        if status == "processing":
            revision.started_at = now_utc()
        if status in {"completed", "failed"}:
            revision.finished_at = now_utc()
        await self.session.commit()

    async def persist_parser_result(self, revision_id: uuid.UUID, result: Any) -> None:
        try:
            async with self.session.begin():
                revision = await self.get_revision(revision_id)
                if revision is None:
                    raise ValueError(f"revision not found: {revision_id}")

                await self.session.execute(delete(CadMesh).where(CadMesh.revision_id == revision_id))
                await self.session.execute(delete(CadRelation).where(CadRelation.revision_id == revision_id))
                await self.session.execute(delete(CadEntity).where(CadEntity.revision_id == revision_id))

                self.session.add_all(
                    [
                        CadEntity(
                            id=entity.id,
                            revision_id=entity.revision_id,
                            parent_entity_id=entity.parent_entity_id,
                            entity_type=entity.entity_type,
                            source_ref=entity.source_ref,
                            source_index=entity.source_index,
                            name=entity.name,
                            label=entity.label,
                            tree_path=entity.tree_path,
                            sort_order=entity.sort_order,
                            geometry_type=entity.geometry_type,
                            area=entity.area,
                            volume=entity.volume,
                            length=entity.length,
                            center=entity.center,
                            bounding_box=entity.bounding_box,
                            placement=entity.placement,
                            geometry=entity.geometry,
                            metadata_json=entity.metadata,
                            fingerprint=entity.fingerprint,
                        )
                        for entity in result.entities
                    ]
                )
                await self.session.flush()
                self.session.add_all(
                    [
                        CadRelation(
                            id=relation.id,
                            revision_id=relation.revision_id,
                            source_entity_id=relation.source_entity_id,
                            target_entity_id=relation.target_entity_id,
                            relation_type=relation.relation_type,
                            metadata_json=relation.metadata,
                        )
                        for relation in result.relations
                    ]
                )
                self.session.add_all(
                    [
                        CadMesh(
                            id=mesh.id,
                            revision_id=mesh.revision_id,
                            entity_id=mesh.entity_id,
                            mesh_type=mesh.mesh_type,
                            positions=mesh.positions,
                            indices=mesh.indices,
                            normals=mesh.normals,
                            color=mesh.color,
                            linear_deflection=mesh.linear_deflection,
                            angular_deflection=mesh.angular_deflection,
                            vertex_count=mesh.vertex_count,
                            triangle_count=mesh.triangle_count,
                        )
                        for mesh in result.meshes
                    ]
                )
                summary = result.summary
                revision.status = "completed"
                revision.progress = 100
                revision.status_message = "completed"
                revision.error_code = None
                revision.error_message = None
                revision.parser_name = result.parser_name
                revision.parser_version = result.parser_version
                revision.schema_version = result.schema_version
                revision.unit = result.unit
                revision.object_count = int(summary.get("object_count", 0))
                revision.solid_count = int(summary.get("solid_count", 0))
                revision.face_count = int(summary.get("face_count", 0))
                revision.edge_count = int(summary.get("edge_count", 0))
                revision.vertex_count = int(summary.get("vertex_count", 0))
                revision.bounding_box = result.bounding_box
                revision.summary = summary
                revision.parse_manifest = result.parse_manifest
                revision.finished_at = now_utc()
        except Exception as exc:
            await self._mark_revision_failed_after_persist_error(revision_id, exc)
            raise

    async def _mark_revision_failed_after_persist_error(self, revision_id: uuid.UUID, exc: Exception) -> None:
        rollback = getattr(self.session, "rollback", None)
        if rollback:
            await rollback()
        revision = await self.get_revision(revision_id)
        if revision is None:
            return
        revision.status = "failed"
        revision.progress = 100
        revision.status_message = "failed"
        revision.error_code = "persist_failed"
        revision.error_message = str(exc)[:1000]
        revision.finished_at = now_utc()
        await self.session.commit()

    async def fail_interrupted_revisions(self, stale_job_minutes: int, error_code: str) -> int:
        cutoff = now_utc() - timedelta(minutes=stale_job_minutes)
        result = await self.session.execute(
            update(CadModelRevision)
            .where(
                CadModelRevision.status.in_(("queued", "processing")),
                CadModelRevision.updated_at <= cutoff,
            )
            .values(
                status="failed",
                progress=100,
                status_message="failed",
                error_code=error_code,
                error_message="CAD parse job was interrupted by service restart.",
                finished_at=now_utc(),
            )
        )
        await self.session.commit()
        return int(result.rowcount or 0)

    async def list_models(self, page: int, page_size: int, has_build: bool = False) -> tuple[list[CadModel], int]:
        filters = []
        if has_build:
            subq = select(ComponentBuild.cad_model_id).distinct().where(ComponentBuild.cad_model_id.isnot(None)).scalar_subquery()
            filters.append(CadModel.id.in_(subq))
        total = await self.session.scalar(select(func.count()).select_from(CadModel).where(*filters))
        result = await self.session.execute(
            select(CadModel, CadModelRevision)
            .outerjoin(CadModelRevision, CadModel.current_revision_id == CadModelRevision.id)
            .where(*filters)
            .order_by(CadModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.all()), int(total or 0)

    async def list_entities(self, revision_id: uuid.UUID) -> list[CadEntity]:
        result = await self.session.execute(
            select(CadEntity).where(CadEntity.revision_id == revision_id).order_by(CadEntity.tree_path, CadEntity.sort_order)
        )
        return list(result.scalars().all())

    async def list_entities_filtered(
        self,
        revision_id: uuid.UUID,
        *,
        parent_entity_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        geometry_type: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CadEntity], int]:
        filters = [CadEntity.revision_id == revision_id]
        if parent_entity_id:
            filters.append(CadEntity.parent_entity_id == parent_entity_id)
        if entity_type:
            filters.append(CadEntity.entity_type == entity_type)
        if geometry_type:
            filters.append(CadEntity.geometry_type == geometry_type)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(CadEntity.source_ref.ilike(pattern), CadEntity.name.ilike(pattern), CadEntity.label.ilike(pattern)))

        total = await self.session.scalar(select(func.count()).select_from(CadEntity).where(*filters))
        result = await self.session.execute(
            select(CadEntity)
            .where(*filters)
            .order_by(CadEntity.source_index.nullslast(), CadEntity.tree_path)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def list_child_entities(
        self,
        revision_id: uuid.UUID,
        parent_entity_id: uuid.UUID,
        entity_type: str | None = None,
    ) -> list[CadEntity]:
        filters = [CadEntity.revision_id == revision_id, CadEntity.parent_entity_id == parent_entity_id]
        if entity_type:
            filters.append(CadEntity.entity_type == entity_type)
        result = await self.session.execute(
            select(CadEntity).where(*filters).order_by(CadEntity.source_index.nullslast(), CadEntity.tree_path)
        )
        return list(result.scalars().all())

    async def list_meshes_filtered(
        self,
        revision_id: uuid.UUID,
        *,
        entity_id: uuid.UUID | None = None,
        parent_entity_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 1000,
    ) -> tuple[list[CadMesh], int]:
        filters = [CadMesh.revision_id == revision_id]
        statement = select(CadMesh)
        count_statement = select(func.count()).select_from(CadMesh)
        if entity_id:
            filters.append(CadMesh.entity_id == entity_id)
        if parent_entity_id:
            statement = statement.join(CadEntity, CadEntity.id == CadMesh.entity_id)
            count_statement = count_statement.join(CadEntity, CadEntity.id == CadMesh.entity_id)
            filters.append(CadEntity.parent_entity_id == parent_entity_id)

        total = await self.session.scalar(count_statement.where(*filters))
        result = await self.session.execute(
            statement.where(*filters).order_by(CadMesh.created_at).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_related_entities(
        self,
        revision_id: uuid.UUID,
        source_entity_id: uuid.UUID,
        relation_type: str,
    ) -> list[CadEntity]:
        result = await self.session.execute(
            select(CadEntity)
            .join(CadRelation, CadRelation.target_entity_id == CadEntity.id)
            .where(
                CadRelation.revision_id == revision_id,
                CadRelation.source_entity_id == source_entity_id,
                CadRelation.relation_type == relation_type,
            )
            .order_by(CadEntity.source_index.nullslast(), CadEntity.tree_path)
        )
        return list(result.scalars().all())

    async def get_source_entities_for_target(
        self,
        revision_id: uuid.UUID,
        target_entity_id: uuid.UUID,
        relation_type: str,
    ) -> list[CadEntity]:
        result = await self.session.execute(
            select(CadEntity)
            .join(CadRelation, CadRelation.source_entity_id == CadEntity.id)
            .where(
                CadRelation.revision_id == revision_id,
                CadRelation.target_entity_id == target_entity_id,
                CadRelation.relation_type == relation_type,
            )
            .order_by(CadEntity.source_index.nullslast(), CadEntity.tree_path)
        )
        return list(result.scalars().all())
