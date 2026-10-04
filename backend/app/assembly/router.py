"""Bounded assembly analysis through the existing build and revision API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.assembly.context import AssemblyContextError
from app.assembly.service import AssemblyAnalysisService
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.measurement.geometry_snapshot import GeometryReferenceError


router = APIRouter(prefix="/api/component-builds/{build_id}/assembly", tags=["assembly"])


class AnalyzeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_ids: list[str] | None = Field(default=None, max_length=64)
    candidate_distance_mm: float = Field(default=10.0, ge=0, le=10000)
    tolerance_mm: float = Field(default=0.01, gt=0, le=0.1)
    source_policy: str = "auxiliary_brep"


def get_assembly_service(session: AsyncSession = Depends(get_session)) -> AssemblyAnalysisService:
    return AssemblyAnalysisService(session)


def _error(exc: ValueError) -> HTTPException:
    code, _, detail = str(exc).partition(":")
    return HTTPException(status_code=409 if code in {"analysis_unavailable", "instance_geometry_mapping_unavailable",
                                                       "stale_reference", "geometry_unavailable"} else 400,
                         detail={"code": code, "message": detail.strip() or str(exc)})


@router.post("/analyze")
async def analyze(build_id: UUID, payload: AnalyzeIn,
                  service: AssemblyAnalysisService = Depends(get_assembly_service),
                  settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.analyze(build_id, settings, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except (AssemblyContextError, GeometryReferenceError) as exc:
        raise _error(exc) from exc


@router.get("/relations")
async def relations(build_id: UUID, offset: int = Query(default=0, ge=0),
                    limit: int = Query(default=50, ge=1, le=200),
                    contact_kind: str | None = None,
                    service: AssemblyAnalysisService = Depends(get_assembly_service)) -> dict:
    try:
        return await service.list_relations(build_id, offset=offset, limit=limit, contact_kind=contact_kind)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc


@router.get("/relations/{relation_id}")
async def relation_detail(build_id: UUID, relation_id: str,
                          service: AssemblyAnalysisService = Depends(get_assembly_service)) -> dict:
    try:
        return await service.relation_detail(build_id, relation_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc
