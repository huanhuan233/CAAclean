"""Build-scoped HTTP surface for the shared geometry query capability."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.measurement.geometry_snapshot import GeometryReferenceError
from app.measurement.repository import MeasurementRepository
from app.measurement.service import MeasurementService


router = APIRouter(prefix="/api/component-builds/{build_id}/geometry", tags=["geometry"])


class GeometryReferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: str
    geometry_snapshot_id: str
    entity_id: str
    asset_sha256: str | None = None


class GeometryQueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    references: list[GeometryReferenceIn] = Field(min_length=1, max_length=2)
    parameters: dict[str, Any] = Field(default_factory=dict)
    source_policy: str = "auxiliary_brep"


def get_measurement_service(session: AsyncSession = Depends(get_session)) -> MeasurementService:
    return MeasurementService(MeasurementRepository(session))


@router.get("/snapshot")
async def geometry_snapshot(build_id: UUID, service: MeasurementService = Depends(get_measurement_service),
                            settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.geometry_context(build_id, settings)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found", "message": str(exc)}) from exc
    except GeometryReferenceError as exc:
        code, _, message = str(exc).partition(":")
        raise HTTPException(status_code=409, detail={"code": code, "message": message.strip()}) from exc


@router.post("/query")
async def geometry_query(build_id: UUID, payload: GeometryQueryIn,
                         service: MeasurementService = Depends(get_measurement_service),
                         settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.query_geometry(build_id, payload.model_dump(), settings)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found", "message": str(exc)}) from exc


@router.get("/results")
async def geometry_results(build_id: UUID, service: MeasurementService = Depends(get_measurement_service)) -> dict:
    context = await service.repository.get_build_context(build_id)
    if context is None:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"})
    rows = await service.repository.list_interactive_results(context[1].id)
    return {"items": [{"result_id": str(row.id), "operation": row.measurement_type,
                       "status": (row.metadata_json or {}).get("status"),
                       "result": row.raw_value} for row in rows]}


@router.get("/results/{result_id}")
async def geometry_result(build_id: UUID, result_id: UUID,
                          service: MeasurementService = Depends(get_measurement_service)) -> dict:
    context = await service.repository.get_build_context(build_id)
    if context is None:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"})
    row = await service.repository.get_measurement(result_id)
    if row is None or row.revision_id != context[1].id or row.algorithm_version not in {"interactive.p1.v1", "interactive.p1.v2"}:
        raise HTTPException(status_code=404, detail={"code": "result_not_found"})
    return {"result_id": str(row.id), **row.raw_value}
