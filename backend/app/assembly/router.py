"""Bounded assembly analysis through the existing build and revision API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.assembly.context import AssemblyContextError
from app.assembly.service import AssemblyAnalysisService
from app.assembly.connections import ConnectionService
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
    minimum_lap_fraction: float = Field(default=0.5, gt=0, le=1)


class BooleanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shell_instance_id: str = Field(min_length=1, max_length=128)
    other_instance_id: str = Field(min_length=1, max_length=128)
    operation: str
    purpose: str = Field(min_length=1, max_length=256)


def get_assembly_service(session: AsyncSession = Depends(get_session)) -> AssemblyAnalysisService:
    return AssemblyAnalysisService(session)


def get_connection_service(session: AsyncSession = Depends(get_session)) -> ConnectionService:
    return ConnectionService(session)


def _error(exc: ValueError) -> HTTPException:
    code, _, detail = str(exc).partition(":")
    return HTTPException(status_code=409 if code in {"analysis_unavailable", "instance_geometry_mapping_unavailable",
                                                       "stale_reference", "geometry_unavailable",
                                                       "connection_source_unavailable"} else 400,
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


@router.post("/booleans")
async def derive_boolean(build_id: UUID, payload: BooleanIn,
                         service: AssemblyAnalysisService = Depends(get_assembly_service),
                         settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.derive_boolean(build_id, settings, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except (AssemblyContextError, GeometryReferenceError) as exc:
        raise _error(exc) from exc


@router.get("/booleans")
async def booleans(build_id: UUID, offset: int = Query(default=0, ge=0),
                   limit: int = Query(default=50, ge=1, le=200),
                   service: AssemblyAnalysisService = Depends(get_assembly_service)) -> dict:
    try:
        return await service.list_booleans(build_id, offset=offset, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc


@router.get("/connections")
async def connections(build_id: UUID, offset: int = Query(default=0, ge=0),
                      limit: int = Query(default=50, ge=1, le=200), kind: str | None = None,
                      service: ConnectionService = Depends(get_connection_service)) -> dict:
    try:
        return await service.list(build_id, offset=offset, limit=limit, kind=kind)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc


@router.get("/connections/{connection_id}")
async def connection_detail(build_id: UUID, connection_id: str,
                            service: ConnectionService = Depends(get_connection_service)) -> dict:
    try:
        return await service.detail(build_id, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc
