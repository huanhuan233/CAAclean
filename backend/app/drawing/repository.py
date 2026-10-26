# 图纸任务、源图和区域的内存/数据库存储层，区域替换保留被取代的历史记录。
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadDrawingRegion, CadSpecSource, CadSpecTask


# 返回带 UTC 时区的当前时间，供需要统一时间基准的调用方使用。
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# 内存实现中的图纸任务记录，包含目标型号和 DN。
@dataclass
class MemoryTask:
    id: uuid.UUID
    revision_id: uuid.UUID | None
    status: str = "created"
    error_code: str | None = None
    error_message: str | None = None
    target_code: str | None = None
    target_dn: str | None = None


# 保存内存任务的源文件身份、路径和预处理元数据。
@dataclass
class MemorySource:
    id: uuid.UUID
    task_id: uuid.UUID
    file_path: str
    file_name: str
    sha256: str
    mime_type: str
    metadata: dict = field(default_factory=dict)


# 模拟区域数据库记录，包含原始框、扩边框、裁剪文件及有效状态。
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


# 提供无数据库的图纸仓库实现，适合隔离验证流程。
class MemoryDrawingRepository:
    # 初始化按 UUID 索引的任务、源图及区域记录容器。
    def __init__(self):
        self.tasks: dict[uuid.UUID, MemoryTask] = {}
        self.sources: dict[uuid.UUID, MemorySource] = {}
        self.regions: list[MemoryRegion] = []

    # 创建关联的任务和源图，保留调用方传入的目标标识。
    async def create_task(self, *, revision_id, source_path: Path, source_sha256: str, mime_type: str, target_code, target_dn):
        task = MemoryTask(uuid.uuid4(), revision_id, target_code=target_code, target_dn=target_dn)
        source = MemorySource(uuid.uuid4(), task.id, str(source_path), source_path.name, source_sha256, mime_type)
        self.tasks[task.id] = task
        self.sources[source.id] = source
        return task, source

    # 按 UUID 取内存任务，未找到时返回空值。
    async def get_task(self, task_id):
        return self.tasks.get(task_id)

    # 查找任务关联的首个内存源图。
    async def get_source_for_task(self, task_id):
        return next((source for source in self.sources.values() if source.task_id == task_id), None)

    # 同步替换任务状态及错误信息。
    async def update_task_status(self, task_id, status, error_code=None, error_message=None):
        task = self.tasks[task_id]
        task.status = status
        task.error_code = error_code
        task.error_message = error_message

    # 以新字典替换源图预处理元数据。
    async def update_source_metadata(self, source_id, metadata):
        self.sources[source_id].metadata = metadata

    # 将任务现有有效区域标记为 superseded，再追加新区域。
    async def replace_regions(self, task_id, regions):
        for region in self.regions:
            if region.task_id == task_id and region.status == "active":
                region.status = "superseded"
        self.regions.extend(regions)

    # 仅返回任务当前处于 active 状态的区域。
    async def list_active_regions(self, task_id):
        return [region for region in self.regions if region.task_id == task_id and region.status == "active"]

    # 可按修订筛选任务，并按 UUID 文本排序。
    async def list_tasks(self, revision_id=None):
        tasks = list(self.tasks.values())
        if revision_id is not None:
            tasks = [task for task in tasks if task.revision_id == revision_id]
        return sorted(tasks, key=lambda task: str(task.id))


# 以异步 SQLAlchemy 会话持久化图纸任务与区域。
class SqlAlchemyDrawingRepository:
    # 接收请求或后台任务独享的数据库会话。
    def __init__(self, session: AsyncSession):
        self.session = session

    # 先创建任务获取主键，再保存源图并提交；此实现未持久化传入的目标型号和 DN。
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

    # 按主键获取任务数据库记录。
    async def get_task(self, task_id):
        return await self.session.get(CadSpecTask, task_id)

    # 按创建时间倒序选择任务最新源记录。
    async def get_source_for_task(self, task_id):
        result = await self.session.execute(select(CadSpecSource).where(CadSpecSource.task_id == task_id).order_by(CadSpecSource.created_at.desc()))
        return result.scalars().first()

    # 更新状态和错误；布局就绪、人工待办或失败时将进度置为 100。
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

    # 替换源记录的 JSON 元数据并提交，源记录缺失时直接返回。
    async def update_source_metadata(self, source_id, metadata):
        source = await self.session.get(CadSpecSource, source_id)
        if source is None:
            return
        source.metadata_json = metadata
        await self.session.commit()

    # 在一次事务内淘汰旧有效区域并保存新区，失败时回滚。
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

    # 按显示顺序返回任务的有效区域。
    async def list_active_regions(self, task_id):
        result = await self.session.execute(
            select(CadDrawingRegion).where(CadDrawingRegion.task_id == task_id, CadDrawingRegion.status == "active").order_by(CadDrawingRegion.sort_order)
        )
        return list(result.scalars().all())

    # 可按修订过滤，并按创建时间倒序查询任务。
    async def list_tasks(self, revision_id=None):
        clauses = []
        if revision_id is not None:
            clauses.append(CadSpecTask.revision_id == revision_id)
        result = await self.session.execute(select(CadSpecTask).where(*clauses).order_by(CadSpecTask.created_at.desc()))
        return list(result.scalars().all())


# 将源图复制到专属目录的规范文件名，源和目标相同时跳过复制。
def copy_source_to_task_dir(source_path: Path, task_dir: Path) -> Path:
    task_dir.mkdir(parents=True, exist_ok=True)
    target = task_dir / f"source{source_path.suffix.lower()}"
    if source_path.resolve() != target.resolve():
        shutil.copyfile(source_path, target)
    return target
