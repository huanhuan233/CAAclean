from __future__ import annotations

import uuid
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadDrawingRegion, CadDrawingFact, CadEntity, CadModel, CadModelRevision, CadSpecSource, CadSpecTask, ComponentBuild, ComponentSpecDraft, utc_now


class MemoryComponentBuildRepository:
    def __init__(self, *, revision_models: dict[uuid.UUID, uuid.UUID] | None = None, drawing_task_revisions: dict[uuid.UUID, uuid.UUID] | None = None):
        self.builds: dict[uuid.UUID, ComponentBuild] = {}
        self.component_specs: dict[uuid.UUID, ComponentSpecDraft] = {}
        self.revision_models = revision_models
        self.drawing_task_revisions = drawing_task_revisions

    async def create_build(self, **fields) -> ComponentBuild:
        now = utc_now()
        fields.setdefault("id", uuid.uuid4())
        fields.setdefault("status", "draft")
        fields.setdefault("version", "1.0.0")
        fields.setdefault("created_at", now)
        fields.setdefault("updated_at", now)
        build = ComponentBuild(**fields)
        self.builds[build.id] = build
        return build

    async def get_build(self, build_id: uuid.UUID) -> ComponentBuild | None:
        return self.builds.get(build_id)

    async def update_build(self, build_id: uuid.UUID, **fields) -> ComponentBuild:
        build = await self._require_build(build_id)
        for name, value in fields.items():
            setattr(build, name, value)
        build.updated_at = utc_now()
        return build

    async def list_builds(self) -> list[ComponentBuild]:
        return sorted(self.builds.values(), key=lambda build: (build.created_at, str(build.id)), reverse=True)

    async def list_structure_entities(self, revision_id: uuid.UUID) -> list:
        """用途：内存仓储没有 CAD 实体表时返回空结构，保持旧单元测试向前兼容。"""
        return []

    async def next_component_id(self, prefix: str) -> str:
        return _next_component_id(prefix, (build.component_id for build in self.builds.values()))

    async def get_component_spec(self, build_id: uuid.UUID) -> ComponentSpecDraft | None:
        await self._require_build(build_id)
        return self.component_specs.get(build_id)

    async def save_component_spec(self, build_id: uuid.UUID, data: dict) -> ComponentSpecDraft:
        await self._require_build(build_id)
        now = utc_now()
        draft = self.component_specs.get(build_id)
        if draft is None:
            draft = ComponentSpecDraft(
                build_id=build_id,
                schema_version="1.2",
                data=data,
                created_at=now,
                updated_at=now,
            )
            self.component_specs[build_id] = draft
        else:
            draft.data = data
            draft.updated_at = now
        return draft

    async def attach_step(self, build_id: uuid.UUID, *, model_id: uuid.UUID, revision_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        if self.revision_models is not None and self.revision_models.get(revision_id) != model_id:
            raise ValueError("revision does not belong to model")
        if build.cad_revision_id != revision_id:
            build.drawing_task_id = None
        build.cad_model_id = model_id
        build.cad_revision_id = revision_id
        build.updated_at = utc_now()
        return build

    async def attach_drawing(self, build_id: uuid.UUID, *, task_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        if build.cad_revision_id is None or (
            self.drawing_task_revisions is not None and self.drawing_task_revisions.get(task_id) != build.cad_revision_id
        ):
            raise ValueError("drawing task does not belong to build revision")
        build.drawing_task_id = task_id
        build.updated_at = utc_now()
        return build

    async def set_status(
        self,
        build_id: uuid.UUID,
        *,
        status: str,
        message: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        build = await self._require_build(build_id)
        build.status = status
        build.status_message = message
        build.error_code = error_code
        build.error_message = error_message
        build.updated_at = utc_now()

    async def delete_build(self, build_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        del self.builds[build.id]
        return build

    async def _require_build(self, build_id: uuid.UUID) -> ComponentBuild:
        build = await self.get_build(build_id)
        if build is None:
            raise ValueError(f"component build not found: {build_id}")
        return build


class SqlAlchemyComponentBuildRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_build(self, **fields) -> ComponentBuild:
        build = ComponentBuild(**fields)
        self.session.add(build)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(build)
        return build

    async def get_build(self, build_id: uuid.UUID) -> ComponentBuild | None:
        return await self.session.get(ComponentBuild, build_id)

    async def update_build(self, build_id: uuid.UUID, **fields) -> ComponentBuild:
        build = await self._require_build(build_id)
        for name, value in fields.items():
            setattr(build, name, value)
        await self.session.commit()
        await self.session.refresh(build)
        return build

    async def list_builds(self) -> list[ComponentBuild]:
        result = await self.session.execute(select(ComponentBuild).order_by(ComponentBuild.created_at.desc(), ComponentBuild.id.desc()))
        return list(result.scalars().all())

    async def list_structure_entities(self, revision_id: uuid.UUID) -> list[CadEntity]:
        """用途：为统一 Viewer 读取真实结构节点，不把 Face/Edge 等海量拓扑塞入 BOM。"""
        result = await self.session.execute(
            select(CadEntity)
            .where(
                CadEntity.revision_id == revision_id,
                CadEntity.entity_type.in_({"root", "assembly", "subassembly", "part", "imported_object", "body", "solid"}),
            )
            .order_by(CadEntity.sort_order, CadEntity.id)
        )
        return list(result.scalars().all())

    async def next_component_id(self, prefix: str) -> str:
        result = await self.session.execute(select(ComponentBuild.component_id))
        return _next_component_id(prefix, result.scalars().all())

    async def get_component_spec(self, build_id: uuid.UUID) -> ComponentSpecDraft | None:
        await self._require_build(build_id)
        return await self.session.get(ComponentSpecDraft, build_id)

    async def save_component_spec(self, build_id: uuid.UUID, data: dict) -> ComponentSpecDraft:
        await self._require_build(build_id)
        draft = await self.session.get(ComponentSpecDraft, build_id)
        if draft is None:
            draft = ComponentSpecDraft(build_id=build_id, schema_version="1.2", data=data)
            self.session.add(draft)
        else:
            draft.data = data
            draft.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(draft)
        return draft

    async def attach_step(self, build_id: uuid.UUID, *, model_id: uuid.UUID, revision_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        revision = await self.session.get(CadModelRevision, revision_id)
        if revision is None or revision.model_id != model_id:
            raise ValueError("revision does not belong to model")
        if build.cad_revision_id != revision_id:
            build.drawing_task_id = None
        build.cad_model_id = model_id
        build.cad_revision_id = revision_id
        await self.session.commit()
        await self.session.refresh(build)
        return build

    async def attach_drawing(self, build_id: uuid.UUID, *, task_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        task = await self.session.get(CadSpecTask, task_id)
        if build.cad_revision_id is None or task is None or task.revision_id != build.cad_revision_id:
            raise ValueError("drawing task does not belong to build revision")
        build.drawing_task_id = task_id
        await self.session.commit()
        await self.session.refresh(build)
        return build

    async def set_status(
        self,
        build_id: uuid.UUID,
        *,
        status: str,
        message: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        build = await self._require_build(build_id)
        build.status = status
        build.status_message = message
        build.error_code = error_code
        build.error_message = error_message
        await self.session.commit()

    async def delete_build(self, build_id: uuid.UUID) -> ComponentBuild:
        """Delete a component build record. Returns the build before deletion."""
        build = await self._require_build(build_id)
        await self.session.delete(build)
        await self.session.commit()
        return build

    # 用途：为 service.delete_build 提供资源清理所需的查询方法。

    async def list_drawing_sources(self, task_id: uuid.UUID) -> list[dict]:
        result = await self.session.execute(
            select(CadSpecSource).where(CadSpecSource.task_id == task_id)
        )
        rows = result.scalars().all()
        return [{"id": str(r.id), "file_path": r.file_path, "file_name": r.file_name} for r in rows]

    async def list_drawing_regions(self, task_id: uuid.UUID) -> list[dict]:
        result = await self.session.execute(
            select(CadDrawingRegion).where(CadDrawingRegion.task_id == task_id)
        )
        rows = result.scalars().all()
        return [{"id": str(r.id), "crop_file_path": r.crop_file_path} for r in rows]

    async def get_raw_revision(self, revision_id: uuid.UUID) -> CadModelRevision | None:
        return await self.session.get(CadModelRevision, revision_id)

    async def list_builds_by_model(self, model_id: uuid.UUID, *, exclude_build_id: uuid.UUID | None = None) -> list[ComponentBuild]:
        stmt = select(ComponentBuild).where(ComponentBuild.cad_model_id == model_id)
        if exclude_build_id:
            stmt = stmt.where(ComponentBuild.id != exclude_build_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _require_build(self, build_id: uuid.UUID) -> ComponentBuild:
        build = await self.get_build(build_id)
        if build is None:
            raise ValueError(f"component build not found: {build_id}")
        return build


def _next_component_id(prefix: str, component_ids) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    sequence = 0
    for component_id in component_ids:
        match = pattern.match(component_id)
        if match:
            sequence = max(sequence, int(match.group(1)))
    return f"{prefix}-{sequence + 1:03d}"
