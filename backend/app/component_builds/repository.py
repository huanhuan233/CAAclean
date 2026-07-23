from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ComponentBuild, utc_now


class MemoryComponentBuildRepository:
    def __init__(self):
        self.builds: dict[uuid.UUID, ComponentBuild] = {}

    async def create_build(self, **fields) -> ComponentBuild:
        now = utc_now()
        build = ComponentBuild(
            id=uuid.uuid4(),
            status="draft",
            version="1.0.0",
            created_at=now,
            updated_at=now,
            **fields,
        )
        self.builds[build.id] = build
        return build

    async def get_build(self, build_id: uuid.UUID) -> ComponentBuild | None:
        return self.builds.get(build_id)

    async def list_builds(self) -> list[ComponentBuild]:
        return sorted(self.builds.values(), key=lambda build: str(build.id))

    async def attach_step(self, build_id: uuid.UUID, *, model_id: uuid.UUID, revision_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        build.cad_model_id = model_id
        build.cad_revision_id = revision_id
        build.updated_at = utc_now()
        return build

    async def attach_drawing(self, build_id: uuid.UUID, *, task_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
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
        result = await self.session.execute(select(ComponentBuild).order_by(ComponentBuild.created_at.desc()))
        return list(result.scalars().all())

    async def attach_step(self, build_id: uuid.UUID, *, model_id: uuid.UUID, revision_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        build.cad_model_id = model_id
        build.cad_revision_id = revision_id
        await self.session.commit()
        await self.session.refresh(build)
        return build

    async def attach_drawing(self, build_id: uuid.UUID, *, task_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
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
