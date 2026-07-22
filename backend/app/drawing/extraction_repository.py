from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadDrawingFact, CadSpecTask
from app.drawing.extraction_schemas import DrawingExtractionResult, DrawingFact


@dataclass
class MemoryExtractionRepository:
    crop_packages: dict[str, dict] = field(default_factory=dict)
    results: dict[str, DrawingExtractionResult] = field(default_factory=dict)
    current_facts: dict[str, list[DrawingFact]] = field(default_factory=dict)
    generation_no: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, dict] = field(default_factory=dict)

    async def get_crop_package(self, task_id):
        return self.crop_packages[str(task_id)]

    async def set_status(self, task_id, status, progress=0, message=None, error_code=None, error_message=None):
        self.statuses[str(task_id)] = {"task_id": str(task_id), "status": status, "error_code": error_code, "error_message": error_message}

    async def get_status(self, task_id):
        return self.statuses.get(str(task_id), {"task_id": str(task_id), "status": "layout_ready", "error_code": None, "error_message": None})

    async def replace_extraction(self, task_id, result: DrawingExtractionResult):
        key = str(task_id)
        self.generation_no[key] = self.generation_no.get(key, 0) + 1
        self.results[key] = result
        self.current_facts[key] = result.facts

    async def get_result(self, task_id):
        return self.results.get(str(task_id))

    async def list_facts(self, task_id, **filters):
        facts = self.current_facts.get(str(task_id), [])
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


class SqlAlchemyExtractionRepository:
    def __init__(self, session: AsyncSession, layout_service):
        self.session = session
        self.layout_service = layout_service

    async def get_crop_package(self, task_id):
        package = await self.layout_service.build_crop_package(task_id)
        return package.model_dump(mode="json")

    async def set_status(self, task_id, status, progress=0, message=None, error_code=None, error_message=None):
        task = await self.session.get(CadSpecTask, uuid.UUID(str(task_id)))
        if task:
            task.status = status
            task.progress = progress
            task.status_message = message or status
            task.error_code = error_code
            task.error_message = error_message
            await self.session.commit()

    async def get_status(self, task_id):
        task = await self.session.get(CadSpecTask, uuid.UUID(str(task_id)))
        return {"task_id": task_id, "status": task.status, "error_code": task.error_code, "error_message": task.error_message}

    async def replace_extraction(self, task_id, result: DrawingExtractionResult):
        task_uuid = uuid.UUID(str(task_id))
        task = await self.session.get(CadSpecTask, task_uuid)
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

    async def get_result(self, task_id):
        task = await self.session.get(CadSpecTask, uuid.UUID(str(task_id)))
        return task.drawing_extraction if task and task.drawing_extraction else None

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
        if filters.get("keyword"):
            rows = [row for row in rows if filters["keyword"] in row.fact_key or filters["keyword"] in str(row.raw_value)]
        page = filters.get("page", 1)
        page_size = filters.get("page_size", 20)
        return rows[(page - 1) * page_size : page * page_size], len(rows)

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
