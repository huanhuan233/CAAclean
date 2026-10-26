# 提供构建范围内的几何快照、查询与交互结果接口，将请求约束和资源不存在状态映射到 HTTP。
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


# 约束客户端几何引用必须携带修订、快照与实体编号，可选指纹用于额外过期校验。
class GeometryReferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: str
    geometry_snapshot_id: str
    entity_id: str
    asset_sha256: str | None = None


# 接收一至两个几何引用和操作参数，默认明确使用辅助 B-Rep 几何来源。
class GeometryQueryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    references: list[GeometryReferenceIn] = Field(min_length=1, max_length=2)
    parameters: dict[str, Any] = Field(default_factory=dict)
    source_policy: str = "auxiliary_brep"


# 用请求注入的异步数据库会话创建仓库及测量服务。
def get_measurement_service(session: AsyncSession = Depends(get_session)) -> MeasurementService:
    return MeasurementService(MeasurementRepository(session))


# 返回构建当前几何快照；构建缺失返回 404，快照失效或不可用返回 409。
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


# 将校验后的请求传给查询服务；几何业务失败保留服务返回的状态，构建缺失映射为 404。
@router.post("/query")
async def geometry_query(build_id: UUID, payload: GeometryQueryIn,
                         service: MeasurementService = Depends(get_measurement_service),
                         settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.query_geometry(build_id, payload.model_dump(), settings)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found", "message": str(exc)}) from exc


# 解析构建修订后列出最近交互结果，并带出原始结果内的业务状态。
@router.get("/results")
async def geometry_results(build_id: UUID, service: MeasurementService = Depends(get_measurement_service)) -> dict:
    context = await service.repository.get_build_context(build_id)
    if context is None:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"})
    rows = await service.repository.list_interactive_results(context[1].id)
    return {"items": [{"result_id": str(row.id), "operation": row.measurement_type,
                       "status": (row.metadata_json or {}).get("status"),
                       "result": row.raw_value} for row in rows]}


# 只允许读取当前构建修订且属于受支持交互算法版本的结果。
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
