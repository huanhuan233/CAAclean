# 导管 HTTP 入口：依赖当前构建对应的 Revision；几何计算和数据库操作委托给业务服务。
# 请求尺寸容差使用毫米；接口返回原生路径、几何测量和安装间隙三个独立来源。

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


# 分析请求约束：一个导管、至多 31 个目标；拒绝额外字段，避免把未知参数默默忽略。
class AnalyzeTubeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tube_instance_id: str = Field(min_length=1, max_length=128)
    target_instance_ids: list[str] = Field(default_factory=list, max_length=31)
    tolerance_mm: float = Field(default=0.01, gt=0, le=0.1)


# 使用请求作用域的数据库会话创建服务，事务边界由服务及 Repository 管理。
def get_tube_service(session: AsyncSession = Depends(get_session)) -> TubeAnalysisService:
    return TubeAnalysisService(session)


# 把可恢复的数据/映射缺失转换为 409，其余业务输入错误转换为 400，并保留诊断代码。
def _error(exc: ValueError) -> HTTPException:
    code, _, detail = str(exc).partition(":")
    return HTTPException(status_code=409 if code in {"analysis_unavailable", "instance_geometry_mapping_unavailable",
                                                       "stale_reference", "geometry_unavailable"} else 400,
                         detail={"code": code, "message": detail.strip() or str(exc)})


# 提交一次限定对象范围的几何分析；目标列表为空时只计算导管自身。
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


# 列出有可信世界坐标 Solid 映射的对象；候选列表本身不证明对象是空心管。
@router.get("/candidates")
async def tube_candidates(build_id: UUID, service: TubeAnalysisService = Depends(get_tube_service),
                          settings: Settings = Depends(get_settings)) -> dict:
    try:
        return await service.list_candidates(build_id, settings)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "build_not_found"}) from exc
    except (AssemblyContextError, GeometryReferenceError) as exc:
        raise _error(exc) from exc


# 分页读取已入库的 CATIA 中心线引用，不在请求中重新解析原生包。
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


# 分页读取已发布的 STEP/B-Rep 导管测量，并附带当前快照一致性状态。
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


# 分页读取已发布的导管外表面与目标实体间隙，不因查询重新启动 FreeCAD。
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
