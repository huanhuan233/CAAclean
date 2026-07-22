from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadDrawingRegion, CadSpecSource, CadSpecTask


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MemoryTask:
    id: uuid.UUID
    revision_id: uuid.UUID | None
    status: str = "created"
    error_code: str | None = None
    error_message: str | None = None
    target_code: str | None = None
    target_dn: str | None = None


@dataclass
class MemorySource:
    id: uuid.UUID
    task_id: uuid.UUID
    file_path: str
    file_name: str
    sha256: str
    mime_type: str
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryRegion:
    id: uuid.UUID
    task_id: uuid.UUID
    source_id: uuid.UUID
    region_type: str
    provider: str
    provider_region_type: str | None
    bbox_normalized: list[float]
    bbox_pixels: list[int]
    padded_bbox_pixels: list[int]
    confidence: float | None
    sort_order: int
    crop_file_path: str | None
    crop_file_name: str | None
    crop_sha256: str | None
    crop_width: int | None
    crop_height: int | None
    raw_provider_result: dict
    metadata_json: dict
    status: str = "active"


class MemoryDrawingRepository:
    def __init__(self):
        self.tasks: dict[uuid.UUID, MemoryTask] = {}
        self.sources: dict[uuid.UUID, MemorySource] = {}
        self.regions: list[MemoryRegion] = []

    async def create_task(self, *, revision_id, source_path: Path, source_sha256: str, mime_type: str, target_code, target_dn):
        task = MemoryTask(uuid.uuid4(), revision_id, target_code=target_code, target_dn=target_dn)
        source = MemorySource(uuid.uuid4(), task.id, str(source_path), source_path.name, source_sha256, mime_type)
        self.tasks[task.id] = task
        self.sources[source.id] = source
        return task, source

    async def get_task(self, task_id):
        return self.tasks.get(task_id)

    async def get_source_for_task(self, task_id):
        return next((source for source in self.sources.values() if source.task_id == task_id), None)

    async def update_task_status(self, task_id, status, error_code=None, error_message=None):
        task = self.tasks[task_id]
        task.status = status
        task.error_code = error_code
        task.error_message = error_message

    async def update_source_metadata(self, source_id, metadata):
        self.sources[source_id].metadata = metadata

    async def replace_regions(self, task_id, regions):
        for region in self.regions:
            if region.task_id == task_id and region.status == "active":
                region.status = "superseded"
        self.regions.extend(regions)

    async def list_active_regions(self, task_id):
        return [region for region in self.regions if region.task_id == task_id and region.status == "active"]


class SqlAlchemyDrawingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, *, revision_id, source_path: Path, source_sha256: str, mime_type: str, target_code, target_dn):
        task = CadSpecTask(
            revision_id=revision_id,
            status="created",
            progress=0,
            status_message="created",
            drawing_extraction={},
            freecad_facts={},
            semantic_result={},
            validation_report={},
        )
        self.session.add(task)
        await self.session.flush()
        source = CadSpecSource(
            task_id=task.id,
            source_type="drawing",
            file_path=str(source_path),
            file_name=source_path.name,
            sha256=source_sha256,
            mime_type=mime_type,
            file_size=source_path.stat().st_size,
            template_text=None,
            metadata_json={},
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(task)
        await self.session.refresh(source)
        return task, source

    async def get_task(self, task_id):
        return await self.session.get(CadSpecTask, task_id)

    async def get_source_for_task(self, task_id):
        result = await self.session.execute(select(CadSpecSource).where(CadSpecSource.task_id == task_id).order_by(CadSpecSource.created_at.desc()))
        return result.scalars().first()

    async def update_task_status(self, task_id, status, error_code=None, error_message=None):
        task = await self.get_task(task_id)
        if task is None:
            return
        task.status = status
        task.status_message = status
        task.error_code = error_code
        task.error_message = error_message
        task.progress = 100 if status in {"layout_ready", "needs_manual_layout", "failed"} else task.progress
        await self.session.commit()

    async def update_source_metadata(self, source_id, metadata):
        source = await self.session.get(CadSpecSource, source_id)
        if source is None:
            return
        source.metadata_json = metadata
        await self.session.commit()

    async def replace_regions(self, task_id, regions):
        try:
            await self.session.execute(
                update(CadDrawingRegion).where(CadDrawingRegion.task_id == task_id, CadDrawingRegion.status == "active").values(status="superseded")
            )
            self.session.add_all(regions)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def list_active_regions(self, task_id):
        result = await self.session.execute(
            select(CadDrawingRegion).where(CadDrawingRegion.task_id == task_id, CadDrawingRegion.status == "active").order_by(CadDrawingRegion.sort_order)
        )
        return list(result.scalars().all())


def copy_source_to_task_dir(source_path: Path, task_dir: Path) -> Path:
    task_dir.mkdir(parents=True, exist_ok=True)
    target = task_dir / f"source{source_path.suffix.lower()}"
    if source_path.resolve() != target.resolve():
        shutil.copyfile(source_path, target)
    return target
