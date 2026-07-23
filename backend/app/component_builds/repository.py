from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadModelRevision, CadSpecTask, ComponentBuild, utc_now


class MemoryComponentBuildRepository:
    def __init__(self, *, revision_models: dict[uuid.UUID, uuid.UUID] | None = None, drawing_task_revisions: dict[uuid.UUID, uuid.UUID] | None = None):
        self.builds: dict[uuid.UUID, ComponentBuild] = {}
        self.revision_models = revision_models or {}
        self.drawing_task_revisions = drawing_task_revisions or {}

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

    async def list_builds(self) -> list[ComponentBuild]:
        return sorted(self.builds.values(), key=lambda build: (build.created_at, str(build.id)), reverse=True)

    async def attach_step(self, build_id: uuid.UUID, *, model_id: uuid.UUID, revision_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        if self.revision_models.get(revision_id) != model_id:
            raise ValueError("revision does not belong to model")
        build.cad_model_id = model_id
        build.cad_revision_id = revision_id
        build.updated_at = utc_now()
        return build

    async def attach_drawing(self, build_id: uuid.UUID, *, task_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        if build.cad_revision_id is None or self.drawing_task_revisions.get(task_id) != build.cad_revision_id:
            raise ValueError("drawing task does not belong to build revision")
        build.drawing_task_id = task_id
        build.updated_at = utc_now()
        return build

    async def set_status(self, build_id: uuid.UUID, *, status: str, message: str | None = None) -> None:
        build = await self._require_build(build_id)
        build.status = status
        build.status_message = message
        build.updated_at = utc_now()

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

    async def list_builds(self) -> list[ComponentBuild]:
        result = await self.session.execute(select(ComponentBuild).order_by(ComponentBuild.created_at.desc(), ComponentBuild.id.desc()))
        return list(result.scalars().all())

    async def attach_step(self, build_id: uuid.UUID, *, model_id: uuid.UUID, revision_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        revision = await self.session.get(CadModelRevision, revision_id)
        if revision is None or revision.model_id != model_id:
            raise ValueError("revision does not belong to model")
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

    async def set_status(self, build_id: uuid.UUID, *, status: str, message: str | None = None) -> None:
        build = await self._require_build(build_id)
        build.status = status
        build.status_message = message
        await self.session.commit()

    async def _require_build(self, build_id: uuid.UUID) -> ComponentBuild:
        build = await self.get_build(build_id)
        if build is None:
            raise ValueError(f"component build not found: {build_id}")
        return build
