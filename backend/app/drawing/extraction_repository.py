# 存储视觉提取结果与当前事实，保留提取代次并支持型号、DN 和证据状态筛选。
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadDrawingFact, CadSpecTask
from app.drawing.extraction_schemas import DrawingExtractionResult, DrawingFact


# 以字典保存裁剪包、提取结果、当前事实及任务状态。
@dataclass
class MemoryExtractionRepository:
    crop_packages: dict[str, dict] = field(default_factory=dict)
    results: dict[str, DrawingExtractionResult] = field(default_factory=dict)
    current_facts: dict[str, list[DrawingFact]] = field(default_factory=dict)
    generation_no: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, dict] = field(default_factory=dict)

    # 按任务键读取预先准备的裁剪包，缺失时由字典抛出异常。
    async def get_crop_package(self, task_id):
        return self.crop_packages[str(task_id)]

    # 保存提取状态与错误；内存实现不记录进度和状态消息。
    async def set_status(self, task_id, status, progress=0, message=None, error_code=None, error_message=None):
        self.statuses[str(task_id)] = {"task_id": str(task_id), "status": status, "error_code": error_code, "error_message": error_message}

    # 读取状态，尚无记录时返回 layout_ready 默认状态。
    async def get_status(self, task_id):
        return self.statuses.get(str(task_id), {"task_id": str(task_id), "status": "layout_ready", "error_code": None, "error_message": None})

    # 递增代次并替换内存中的提取结果和当前事实。
    async def replace_extraction(self, task_id, result: DrawingExtractionResult):
        key = str(task_id)
        self.generation_no[key] = self.generation_no.get(key, 0) + 1
        self.results[key] = result
        self.current_facts[key] = result.facts

    # 读取任务最近一次提取结果。
    async def get_result(self, task_id):
        return self.results.get(str(task_id))

    # 应用目标行及事实条件过滤后分页，同时返回过滤后的总数。
    async def list_facts(self, task_id, **filters):
        facts = self.current_facts.get(str(task_id), [])
        facts = _filter_target_rows(facts, filters)
        if filters.get("fact_type"):
            facts = [fact for fact in facts if fact.fact_type == filters["fact_type"]]
        if filters.get("symbol"):
            facts = [fact for fact in facts if fact.symbol == filters["symbol"]]
        if filters.get("needs_review") is not None:
            facts = [fact for fact in facts if fact.needs_review is filters["needs_review"]]
        if filters.get("keyword"):
            facts = [fact for fact in facts if filters["keyword"] in fact.fact_key or filters["keyword"] in str(fact.raw_value)]
        page = filters.get("page", 1)
        page_size = filters.get("page_size", 20)
        return facts[(page - 1) * page_size : page * page_size], len(facts)


# 在数据库中保存提取代次、事实证据和任务进度。
class SqlAlchemyExtractionRepository:
    # 注入数据库会话与负责组装裁剪包的布局服务。
    def __init__(self, session: AsyncSession, layout_service):
        self.session = session
        self.layout_service = layout_service

    # 从布局服务构造裁剪包并转换为 JSON 兼容字典。
    async def get_crop_package(self, task_id):
        package = await self.layout_service.build_crop_package(task_id)
        return package.model_dump(mode="json")

    # 写入提取阶段、进度、消息和错误信息，任务不存在则不更新。
    async def set_status(self, task_id, status, progress=0, message=None, error_code=None, error_message=None):
        task = await self.session.get(CadSpecTask, uuid.UUID(str(task_id)))
        if task:
            task.status = status
            task.progress = progress
            task.status_message = message or status
            task.error_code = error_code
            task.error_message = error_message
            await self.session.commit()

    # 读取任务的当前状态与错误；调用方应保证任务存在。
    async def get_status(self, task_id):
        task = await self.session.get(CadSpecTask, uuid.UUID(str(task_id)))
        return {"task_id": task_id, "status": task.status, "error_code": task.error_code, "error_message": task.error_message}

    # 在事务中淘汰上一代事实并插入新代次，随后将任务置为待复核。
    async def replace_extraction(self, task_id, result: DrawingExtractionResult):
        task_uuid = uuid.UUID(str(task_id))
        task = await self.session.get(CadSpecTask, task_uuid)
        # 代次参与事实 UUID，旧事实保留 superseded 状态以维持历史证据可追溯性。
        generation = ((task.drawing_extraction or {}).get("generation_no") or 0) + 1
        try:
            await self.session.execute(update(CadDrawingFact).where(CadDrawingFact.task_id == task_uuid, CadDrawingFact.status == "current").values(status="superseded"))
            self.session.add_all([self._fact_row(task_uuid, result.source_id, fact, result, generation) for fact in result.facts])
            if task:
                task.drawing_extraction = result.model_dump(mode="json") | {"generation_no": generation}
                task.status = "review_ready"
                task.progress = 100
                task.status_message = "review_ready"
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    # 返回任务保存的提取 JSON，没有结果时返回空值。
    async def get_result(self, task_id):
        task = await self.session.get(CadSpecTask, uuid.UUID(str(task_id)))
        return task.drawing_extraction if task and task.drawing_extraction else None

    # 先查询当前事实，再以内存过滤目标行和关键词并分页。
    async def list_facts(self, task_id, **filters):
        clauses = [CadDrawingFact.task_id == uuid.UUID(str(task_id)), CadDrawingFact.status == "current"]
        if filters.get("fact_type"):
            clauses.append(CadDrawingFact.fact_type == filters["fact_type"])
        if filters.get("symbol"):
            clauses.append(CadDrawingFact.symbol == filters["symbol"])
        if filters.get("needs_review") is not None:
            clauses.append(CadDrawingFact.needs_review == filters["needs_review"])
        result = await self.session.execute(select(CadDrawingFact).where(*clauses).order_by(CadDrawingFact.fact_key))
        rows = list(result.scalars().all())
        rows = _filter_target_rows(rows, filters)
        if filters.get("keyword"):
            rows = [row for row in rows if filters["keyword"] in row.fact_key or filters["keyword"] in str(row.raw_value)]
        page = filters.get("page", 1)
        page_size = filters.get("page_size", 20)
        return rows[(page - 1) * page_size : page * page_size], len(rows)

    # 将事实与提取版本信息映射为数据库行，ID 包含任务、代次和事实键。
    def _fact_row(self, task_id, source_id, fact: DrawingFact, result, generation):
        return CadDrawingFact(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"{task_id}:{generation}:{fact.fact_key}"),
            task_id=task_id,
            source_id=source_id,
            region_id=fact.source_region_id,
            fact_key=fact.fact_key,
            fact_type=fact.fact_type,
            symbol=fact.symbol,
            label=fact.label,
            operator=fact.operator,
            raw_value=fact.raw_value,
            normalized_value=fact.normalized_value,
            value_type=fact.value_type,
            unit=fact.unit,
            source_bbox_original=fact.source_bbox_original,
            source_bbox_normalized=fact.source_bbox_normalized,
            source_bbox_precision=fact.source_bbox_precision,
            confidence=fact.confidence,
            needs_review=fact.needs_review,
            model_name=result.model_name,
            prompt_version=result.prompt_version,
            generation_no=generation,
            status="current",
            metadata_json=fact.metadata,
        )


# 仅对尺寸事实筛选型号与 DN；产品信息保留，缺失型号不因型号筛选被排除。
def _filter_target_rows(rows, filters: dict):
    target_code = _normalize_code(filters.get("target_code"))
    target_dn = _normalize_dn(filters.get("target_dn"))
    if target_code is None and target_dn is None:
        return rows
    filtered = []
    for row in rows:
        if getattr(row, "fact_type", None) != "dimension":
            filtered.append(row)
            continue
        metadata = _metadata(row)
        row_code = _normalize_code(metadata.get("row_code"))
        row_dn = _normalize_dn(metadata.get("row_dn"))
        if target_code is not None and row_code is not None and row_code != target_code:
            continue
        # DN 筛选要求明确相等；缺失 DN 的尺寸也会被排除。
        if target_dn is not None and row_dn != target_dn:
            continue
        filtered.append(row)
    return filtered


# 兼容 Pydantic 的 metadata 和 ORM 的 metadata_json 字典。
def _metadata(row) -> dict:
    value = getattr(row, "metadata", None)
    if isinstance(value, dict):
        return value
    value = getattr(row, "metadata_json", None)
    return value if isinstance(value, dict) else {}


# 将型号去除首尾空白并大写，空字符串视为未指定。
def _normalize_code(value) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip().upper()


# 移除 DN 文本并转整数；无法解析的输入视为未指定。
def _normalize_dn(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().upper().replace("DN", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return None
