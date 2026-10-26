# 构建级装配分析接口：约束请求预算，分开暴露空间关系、派生布尔和连接语义。
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


# 装配分析输入，限制实例数量、候选距离与计算容差。
class AnalyzeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_ids: list[str] | None = Field(default=None, max_length=64)
    candidate_distance_mm: float = Field(default=10.0, ge=0, le=10000)
    tolerance_mm: float = Field(default=0.01, gt=0, le=0.1)
    source_policy: str = "auxiliary_brep"
    minimum_lap_fraction: float = Field(default=0.5, gt=0, le=1)


# 派生布尔输入，明确两个实例、操作和使用目的。
class BooleanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shell_instance_id: str = Field(min_length=1, max_length=128)
    other_instance_id: str = Field(min_length=1, max_length=128)
    operation: str
    purpose: str = Field(min_length=1, max_length=256)


# 使用当前请求会话创建装配分析服务。
def get_assembly_service(session: AsyncSession = Depends(get_session)) -> AssemblyAnalysisService:
    return AssemblyAnalysisService(session)


# 使用当前请求会话创建连接语义查询服务。
def get_connection_service(session: AsyncSession = Depends(get_session)) -> ConnectionService:
    return ConnectionService(session)


# 将缺失或过期几何等状态转为冲突响应，其余非法输入返回 400。
def _error(exc: ValueError) -> HTTPException:
    code, _, detail = str(exc).partition(":")
    return HTTPException(status_code=409 if code in {"analysis_unavailable", "instance_geometry_mapping_unavailable",
                                                       "stale_reference", "geometry_unavailable",
                                                       "connection_source_unavailable"} else 400,
                         detail={"code": code, "message": detail.strip() or str(exc)})


# 触发有范围和预算限制的装配分析，并保留具体几何引用错误。
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


# 分页查询已发布的空间关系，可按接触类别过滤。
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


# 读取当前结果版本内的一条空间关系。
@router.get("/relations/{relation_id}")
async def relation_detail(build_id: UUID, relation_id: str,
                          service: AssemblyAnalysisService = Depends(get_assembly_service)) -> dict:
    try:
        return await service.relation_detail(build_id, relation_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc


# 显式提交派生布尔任务，输入源几何保持由快照管理。
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


# 读取已保存派生结果，不在列表请求中重新计算。
@router.get("/booleans")
async def booleans(build_id: UUID, offset: int = Query(default=0, ge=0),
                   limit: int = Query(default=50, ge=1, le=200),
                   service: AssemblyAnalysisService = Depends(get_assembly_service)) -> dict:
    try:
        return await service.list_booleans(build_id, offset=offset, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc


# 分页读取连接语义候选，类别条件不改变候选状态。
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


# 读取唯一连接语义对象及其来源。
@router.get("/connections/{connection_id}")
async def connection_detail(build_id: UUID, connection_id: str,
                            service: ConnectionService = Depends(get_connection_service)) -> dict:
    try:
        return await service.detail(build_id, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except AssemblyContextError as exc:
        raise _error(exc) from exc
