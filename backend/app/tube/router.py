"""Tube path, section and installation inspection on the existing build Revision."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.assembly.context import AssemblyContextError
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.measurement.geometry_snapshot import GeometryReferenceError
from app.tube.service import TubeAnalysisService


router = APIRouter(prefix="/api/component-builds/{build_id}/tube", tags=["tube"])


class AnalyzeTubeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tube_instance_id: str = Field(min_length=1, max_length=128)
    target_instance_ids: list[str] = Field(default_factory=list, max_length=31)
    tolerance_mm: float = Field(default=0.01, gt=0, le=0.1)


def get_tube_service(session: AsyncSession = Depends(get_session)) -> TubeAnalysisService:
    return TubeAnalysisService(session)


def _error(exc: ValueError) -> HTTPException:
    code, _, detail = str(exc).partition(":")
    return HTTPException(status_code=409 if code in {"analysis_unavailable", "instance_geometry_mapping_unavailable",
                                                       "stale_reference", "geometry_unavailable"} else 400,
                         detail={"code": code, "message": detail.strip() or str(exc)})


@router.post("/analyze")
async def analyze_tube(build_id: UUID, payload: AnalyzeTubeIn,
                       service: TubeAnalysisService = Depends(get_tube_service),
                       settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.analyze(build_id, settings, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except (AssemblyContextError, GeometryReferenceError) as exc:
        raise _error(exc) from exc


@router.get("/candidates")
async def tube_candidates(build_id: UUID, service: TubeAnalysisService = Depends(get_tube_service),
                          settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.list_candidates(build_id, settings)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except (AssemblyContextError, GeometryReferenceError) as exc:
        raise _error(exc) from exc


@router.get("/paths/native")
async def native_paths(build_id: UUID, offset: int = Query(default=0, ge=0),
                       limit: int = Query(default=50, ge=1, le=200),
                       service: TubeAnalysisService = Depends(get_tube_service)) -> dict:
    try:
        return await service.list_native_paths(build_id, offset=offset, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc


@router.get("/paths/step")
async def step_paths(build_id: UUID, offset: int = Query(default=0, ge=0),
                     limit: int = Query(default=50, ge=1, le=200),
                     service: TubeAnalysisService = Depends(get_tube_service),
                     settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.list_results(build_id, settings, kind="tube_records", offset=offset, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc


@router.get("/clearances")
async def clearances(build_id: UUID, offset: int = Query(default=0, ge=0),
                     limit: int = Query(default=50, ge=1, le=200),
                     service: TubeAnalysisService = Depends(get_tube_service),
                     settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.list_results(build_id, settings, kind="tube_clearances", offset=offset, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc
