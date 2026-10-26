# 提供构建管理、来源上传、规范融合及 Viewer 查询接口，把业务失败映射为稳定 HTTP 错误。
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.cad.router import get_cad_service
from app.cad.service import CadService
from app.component_builds.catalog import catalog_payload
from app.component_builds.ingest import (
    IngestSourceError,
    identify_source,
    redact_local_paths,
    safe_asset_path,
    schedule_ingest,
)
from app.component_builds.fusion import FusionSourceUnavailable
from app.component_builds.fusion_sources import SqlAlchemyFusionSourceReader
from app.component_builds.caa_new_bundle import CaaNewBundleError
from app.component_builds.repository import SqlAlchemyComponentBuildRepository
from app.component_builds.schemas import ComponentBuildFusionIn, ComponentBuildRetryIn, ComponentSpecDraftIn
from app.component_builds.component_spec_document import ComponentSpecDocumentError
from app.component_builds.service import ComponentBuildService, SqlAlchemySourceStatusReader
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, get_session
from app.drawing.extraction_client import VisionModelError
from app.drawing.router import create_drawing_service, get_drawing_service
from app.drawing.schemas import DrawingError
from app.drawing.service import DrawingLayoutService


router = APIRouter(prefix="/api/component-builds", tags=["component-builds"])


# 在同一请求会话中组装构建仓储、来源状态读取器与融合来源读取器。
def get_component_build_service(session: AsyncSession = Depends(get_session)) -> ComponentBuildService:
    return ComponentBuildService(
        SqlAlchemyComponentBuildRepository(session),
        source_status_reader=SqlAlchemySourceStatusReader(session),
        fusion_source_reader=SqlAlchemyFusionSourceReader(session),
    )


# 先校验上传与目录选择，再创建构建并关联来源；已创建记录发生错误时保留失败状态。
@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_component_build(
    category_code: str = Form(...),
    part_type_code: str = Form(...),
    component_name: str = Form(...),
    standard_number: str | None = Form(default=None),
    version: str = Form(default="1.0.0"),
    source_file: UploadFile | None = File(default=None),
    step_file: UploadFile | None = File(default=None),
    drawing_file: UploadFile | None = File(default=None),
    build_service: ComponentBuildService = Depends(get_component_build_service),
    cad_service: CadService = Depends(get_cad_service),
    drawing_service: DrawingLayoutService = Depends(get_drawing_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    _validate_uploads(source_file, step_file, drawing_file)
    build_id: UUID | None = None
    try:
        build = await build_service.create_catalog_build(
            category_code=category_code,
            part_type_code=part_type_code,
            component_name=component_name,
            standard_number=standard_number,
            version=version,
            status="uploading" if source_file or step_file else "draft",
        )
        build_id = UUID(str(build["id"]))
        return await _apply_source_updates(
            build_id,
            build=build,
            component_name=component_name,
            source_file=source_file,
            step_file=step_file,
            drawing_file=drawing_file,
            build_service=build_service,
            cad_service=cad_service,
            drawing_service=drawing_service,
            settings=settings,
        )
    except (DrawingError, ValueError) as exc:
        await _mark_build_failed(build_service, build_id, exc)
        raise HTTPException(status_code=400, detail=_error_detail(exc)) from exc
    except Exception as exc:
        await _mark_build_failed(build_service, build_id, exc)
        raise HTTPException(status_code=500, detail=_error_detail(exc)) from exc


# 确认构建存在后更新目录元数据和上传来源，失败时记录可查询的构建错误。
@router.patch("/{build_id}", status_code=status.HTTP_202_ACCEPTED)
async def update_component_build(
    build_id: UUID,
    category_code: str = Form(...),
    part_type_code: str = Form(...),
    component_name: str = Form(...),
    standard_number: str | None = Form(default=None),
    version: str = Form(default="1.0.0"),
    source_file: UploadFile | None = File(default=None),
    step_file: UploadFile | None = File(default=None),
    drawing_file: UploadFile | None = File(default=None),
    build_service: ComponentBuildService = Depends(get_component_build_service),
    cad_service: CadService = Depends(get_cad_service),
    drawing_service: DrawingLayoutService = Depends(get_drawing_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    _validate_uploads(source_file, step_file, drawing_file)
    await _get_build_or_404(build_service, build_id)
    try:
        build = await build_service.update_catalog_build(
            build_id,
            category_code=category_code,
            part_type_code=part_type_code,
            component_name=component_name,
            standard_number=standard_number,
            version=version,
        )
        return await _apply_source_updates(
            build_id,
            build=build,
            component_name=component_name,
            source_file=source_file,
            step_file=step_file,
            drawing_file=drawing_file,
            build_service=build_service,
            cad_service=cad_service,
            drawing_service=drawing_service,
            settings=settings,
        )
    except (DrawingError, ValueError) as exc:
        await _mark_build_failed(build_service, build_id, exc)
        raise HTTPException(status_code=400, detail=_error_detail(exc)) from exc
    except Exception as exc:
        await _mark_build_failed(build_service, build_id, exc)
        raise HTTPException(status_code=500, detail=_error_detail(exc)) from exc


# 返回按图元库、分类、零件类型及构建版本组织的目录树。
@router.get("/tree")
async def component_build_tree(service: ComponentBuildService = Depends(get_component_build_service)) -> list[dict]:
    return await service.get_tree()


# 返回服务器定义的可选目录与稳定节点 ID。
@router.get("/catalog")
async def component_build_catalog() -> dict:
    return catalog_payload()


# 按构建 ID 读取聚合详情，不存在时转换为 404。
@router.get("/{build_id}")
async def component_build(build_id: UUID, service: ComponentBuildService = Depends(get_component_build_service)) -> dict:
    return await _get_build_or_404(service, build_id)


# 调用资源清理服务删除构建，区分不存在与清理失败两类响应。
@router.delete("/{build_id}", status_code=status.HTTP_200_OK)
async def delete_component_build(
    build_id: UUID,
    service: ComponentBuildService = Depends(get_component_build_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Delete a component build and all associated resources (CAD model, drawings, specs, files)."""
    try:
        return await service.delete_build(build_id, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "component_build_delete_failed", "message": str(exc)}) from exc


# 读取模型与图纸来源共同投影的进度状态，构建不存在返回 404。
@router.get("/{build_id}/status")
async def component_build_status(build_id: UUID, service: ComponentBuildService = Depends(get_component_build_service)) -> dict:
    try:
        return await service.get_status(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


# 读取 Viewer 能力和资产 URL 契约，缺失来源或版本时返回 404。
@router.get("/{build_id}/viewer")
async def component_build_viewer(
    build_id: UUID,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_viewer_contract(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "viewer_not_found", "message": str(exc)}) from exc


# 仅允许下载已就绪且列在发布清单中的资产，并限制路径在当前任务目录内。
@router.get("/{build_id}/viewer/assets/{asset_path:path}")
async def component_build_viewer_asset(
    build_id: UUID,
    asset_path: str,
    service: ComponentBuildService = Depends(get_component_build_service),
    settings: Settings = Depends(get_settings),
):
    contract = await component_build_viewer(build_id, service)
    if contract.get("status") != "ready":
        raise HTTPException(status_code=409, detail={"code": "VIEWER_ASSET_NOT_READY", "message": "模型尚未处理完成"})
    urls = [value for value in (contract.get("viewer_asset") or {}).values() if value]
    urls.extend(value for key, value in (contract.get("feature_center") or {}).items() if key.endswith("_url") and value)
    urls.extend(value for key, value in (contract.get("native_semantics") or {}).items() if key.endswith("_url") and value)
    requested_suffix = f"/viewer/assets/{asset_path}"
    if not any(str(url).endswith(requested_suffix) for url in urls):
        raise HTTPException(status_code=404, detail={"code": "VIEWER_ASSET_NOT_LISTED", "message": "资产不在发布清单中"})
    path = safe_asset_path(Path(settings.cad_work_dir) / contract["task_id"], asset_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"code": "VIEWER_ASSET_MISSING", "message": "资产文件不存在"})
    media_type = "model/gltf-binary" if path.suffix.lower() == ".glb" else "application/json"
    return FileResponse(path, media_type=media_type, filename=path.name)


# 透传父节点、可见性和分页参数，查询已落库原生树的一层节点。
@router.get("/{build_id}/viewer/native/tree")
async def component_build_native_tree(
    build_id: UUID,
    include_supplemental: bool = False,
    parent_id: str | None = None,
    offset: int = Query(0, ge=0),
    page_size: int | None = Query(None, ge=1, le=500),
    service: ComponentBuildService = Depends(get_component_build_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await service.get_native_tree(
            build_id,
            settings,
            include_supplemental=include_supplemental,
            parent_id=parent_id,
            offset=offset,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_TREE_NOT_FOUND", "message": str(exc)}) from exc


# 查询单个原生树节点，区分节点缺失与整树不可用错误。
@router.get("/{build_id}/viewer/native/nodes/{node_id}")
async def component_build_native_node(
    build_id: UUID,
    node_id: str,
    service: ComponentBuildService = Depends(get_component_build_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await service.get_native_node(build_id, node_id, settings)
    except CaaNewBundleError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_NODE_NOT_FOUND", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_TREE_NOT_FOUND", "message": str(exc)}) from exc


# 查询原生节点属性页签与语义详情，缺失节点或属性时给出明确错误码。
@router.get("/{build_id}/viewer/native/nodes/{node_id}/properties")
async def component_build_native_node_properties(
    build_id: UUID,
    node_id: str,
    service: ComponentBuildService = Depends(get_component_build_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await service.get_native_node_properties(build_id, node_id, settings)
    except CaaNewBundleError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_PROPERTIES_NOT_FOUND", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_TREE_NOT_FOUND", "message": str(exc)}) from exc


# 读取当前构建关联版本的原生拓扑和几何记录，缺失时返回 404。
@router.get("/{build_id}/viewer/native/topology")
async def component_build_native_topology(
    build_id: UUID,
    service: ComponentBuildService = Depends(get_component_build_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await service.get_native_topology(build_id, settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_TOPOLOGY_NOT_FOUND", "message": str(exc)}) from exc


# 按通道分页读取 DXF 数据，传 object_id 时改为精确对象查询。
@router.get("/{build_id}/viewer/dxf/{kind}")
async def component_build_dxf_records(
    build_id: UUID,
    kind: str,
    offset: int = Query(0, ge=0),
    page_size: int = Query(200, ge=1, le=1000),
    object_id: str | None = None,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        if object_id:
            return await service.get_dxf_record(build_id, kind, object_id)
        return await service.get_dxf_records(build_id, kind, offset, page_size)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "DXF_RECORD_NOT_FOUND", "message": str(exc)}) from exc


# 按通道和分页参数查询已发布证据，禁止将未采集通道当作空结果。
@router.get("/{build_id}/viewer/native/evidence/{kind}")
async def component_build_native_evidence(
    build_id: UUID,
    kind: str,
    offset: int = Query(0, ge=0),
    page_size: int = Query(1000, ge=1, le=5000),
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_native_evidence(build_id, kind, offset, page_size)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_EVIDENCE_NOT_FOUND", "message": str(exc)}) from exc


# 读取当前版本指定铺层组已发布的覆盖结果，缺失或过期时返回 404。
@router.get("/{build_id}/viewer/composites/coverage/{group_id}")
async def component_build_composite_coverage(
    build_id: UUID,
    group_id: str,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_composite_coverage(build_id, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "COMPOSITE_COVERAGE_NOT_FOUND", "message": str(exc)}) from exc


# 以毫米坐标查询覆盖区域；无法使用该点时返回 422。
@router.get("/{build_id}/viewer/composites/coverage/{group_id}/at")
async def component_build_composite_coverage_at(
    build_id: UUID,
    group_id: str,
    x_mm: float,
    y_mm: float,
    z_mm: float,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_composite_coverage_at(build_id, group_id, (x_mm, y_mm, z_mm))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "COMPOSITE_POINT_UNAVAILABLE", "message": str(exc)}) from exc


# 显式接收固化或未固化厚度口径，触发该组覆盖重算并报告不可计算原因。
@router.post("/{build_id}/viewer/composites/coverage/{group_id}/recompute")
async def recompute_component_build_composite_coverage(
    build_id: UUID,
    group_id: str,
    thickness_basis: str = Query(..., pattern="^(cured|uncured)$"),
    service: ComponentBuildService = Depends(get_component_build_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await service.recompute_composite_coverage(build_id, group_id, thickness_basis, settings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "COMPOSITE_COVERAGE_UNAVAILABLE", "message": str(exc)}) from exc


# 按复材对象定义 ID 查询详情，不用树节点显示名匹配铺层。
@router.get("/{build_id}/viewer/composites/{object_id}")
async def component_build_composite_detail(
    build_id: UUID,
    object_id: str,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_composite_ply_detail(build_id, object_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "COMPOSITE_OBJECT_NOT_FOUND", "message": str(exc)}) from exc


# 接收标注类型、集合、视图、读取状态及文本筛选，返回分页标注。
@router.get("/{build_id}/viewer/mbd/annotations")
async def component_build_mbd_annotations(
    build_id: UUID,
    offset: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=500),
    annotation_kind: str | None = Query(None, max_length=80),
    set_id: str | None = Query(None, max_length=128),
    view_id: str | None = Query(None, max_length=128),
    read_status: str | None = Query(None, max_length=80),
    search: str | None = Query(None, max_length=200),
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.list_mbd_annotations(
            build_id, offset=offset, limit=page_size, annotation_kind=annotation_kind,
            set_id=set_id, view_id=view_id, read_status=read_status, search=search)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "MBD_ANNOTATIONS_NOT_FOUND", "message": str(exc)}) from exc


# 查询唯一标注、关联关系及几何映射状态，缺失时返回 404。
@router.get("/{build_id}/viewer/mbd/annotations/{annotation_id}")
async def component_build_mbd_annotation_detail(
    build_id: UUID,
    annotation_id: str,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_mbd_annotation_detail(build_id, annotation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "MBD_ANNOTATION_NOT_FOUND", "message": str(exc)}) from exc


# 查询 PMI 节点及关联关系，缺失或身份冲突时返回 404。
@router.get("/{build_id}/viewer/mbd/nodes/{pmi_id}")
async def component_build_mbd_node_detail(
    build_id: UUID,
    pmi_id: str,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_mbd_node_detail(build_id, pmi_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "MBD_NODE_NOT_FOUND", "message": str(exc)}) from exc


# 按 Feature Center 身份读取识别特征和测量，缺失时返回 404。
@router.get("/{build_id}/viewer/recognized-features/{feature_center_id}")
async def component_build_recognized_feature_detail(
    build_id: UUID,
    feature_center_id: str,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_recognized_feature_detail(build_id, feature_center_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "RECOGNIZED_FEATURE_NOT_FOUND", "message": str(exc)}) from exc


# 读取原生节点关联的选择候选，映射可信度由服务层判定。
@router.get("/{build_id}/viewer/native/nodes/{node_id}/selection")
async def component_build_native_node_selection(
    build_id: UUID,
    node_id: str,
    service: ComponentBuildService = Depends(get_component_build_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await service.get_native_node_selection(build_id, node_id, settings)
    except CaaNewBundleError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_SELECTION_NOT_FOUND", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NATIVE_TREE_NOT_FOUND", "message": str(exc)}) from exc


# 读取已保存规范文档或空白模板，构建不存在时返回 404。
@router.get("/{build_id}/component-spec")
async def component_spec_draft(build_id: UUID, service: ComponentBuildService = Depends(get_component_build_service)) -> dict:
    try:
        return await service.get_component_spec(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


# 保存规范数据与可选原始 YAML；两者不一致时返回 422。
@router.put("/{build_id}/component-spec")
async def save_component_spec(
    build_id: UUID,
    payload: ComponentSpecDraftIn,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.save_component_spec(
            build_id,
            payload.data,
            yaml_text=payload.yaml,
            source_filename=payload.source_filename,
        )
    except ComponentSpecDocumentError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_component_spec_document", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


# 校验并生成 YAML 预览，不写入规范草稿。
@router.post("/{build_id}/component-spec/preview")
async def preview_component_spec(
    build_id: UUID,
    payload: ComponentSpecDraftIn,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return {
            "yaml": await service.preview_component_spec(
                build_id,
                payload.data,
                yaml_text=payload.yaml,
            )
        }
    except ComponentSpecDocumentError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_component_spec_document", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


# 按覆盖开关融合当前来源，完全无来源时返回冲突状态 409。
@router.post("/{build_id}/fusion")
async def fuse_component_build(
    build_id: UUID,
    payload: ComponentBuildFusionIn,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.fuse_component_spec(build_id, overwrite=payload.overwrite)
    except FusionSourceUnavailable as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "no_sources_available", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "component_build_not_found", "message": str(exc)},
        ) from exc


# 刷新运行配置，按来源角色重排现有版本或图纸任务，保留原任务身份。
@router.post("/{build_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_component_build(
    build_id: UUID,
    payload: ComponentBuildRetryIn,
    service: ComponentBuildService = Depends(get_component_build_service),
    cad_service: CadService = Depends(get_cad_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    get_settings.cache_clear()
    settings = get_settings()
    build = await _get_build_or_404(service, build_id)
    if payload.role == "reference_step":
        if build["cad_revision_id"] is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "step_source_unavailable", "message": "STEP source is not attached"},
            )
        if build.get("processing_route") in {"step_cad_parse", "catia_feature_center", "dxf_cad_parse"}:
            await cad_service.repository.set_revision_status(
                UUID(build["cad_revision_id"]),
                status="queued",
                progress=0,
                status_message="queued",
                error_code=None,
                error_message=None,
            )
            result = await service.set_status(build_id, status="parsing_sources", message="source_retry_queued")
            schedule_ingest(UUID(build["cad_revision_id"]), settings)
            return result
        result = await service.set_status(build_id, status="parsing_sources", message="step_retry_queued")
        schedule_step_pipeline(UUID(build["cad_revision_id"]), cad_service)
        return result
    if build["drawing_task_id"] is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "drawing_retry_unavailable", "message": "drawing source is not attached"},
        )
    result = await service.set_status(build_id, status="parsing_sources", message="drawing_retry_queued")
    schedule_drawing_pipeline(
        UUID(build["drawing_task_id"]),
        settings,
        target_code=build["component_id"],
        target_dn=build["default_dn"],
    )
    return result


# 将旧 STEP 解析入口交给后台协程，HTTP 请求直接返回。
def schedule_step_pipeline(revision_id: UUID, cad_service: CadService) -> None:
    asyncio.create_task(cad_service.parse_revision_in_background(revision_id))


# 把图纸任务及目标构件、DN 信息传给独立后台处理流程。
def schedule_drawing_pipeline(
    task_id: UUID,
    settings: Settings,
    *,
    target_code: str | None,
    target_dn: int | None,
) -> None:
    asyncio.create_task(run_drawing_pipeline(task_id, settings, target_code=target_code, target_dn=target_dn))


# 以新数据库会话先做图纸布局，再抽取事实；只有布局就绪才进入抽取阶段。
async def run_drawing_pipeline(
    task_id: UUID,
    settings: Settings,
    *,
    target_code: str | None,
    target_dn: int | None,
) -> None:
    async with SessionLocal() as session:
        drawing = create_drawing_service(session, settings)
        try:
            layout = await drawing.start_layout(task_id)
        except (DrawingError, VisionModelError):
            return
        except Exception as exc:
            await drawing.repository.update_task_status(task_id, "failed", "layout_failed", str(exc))
            return
        if layout["status"] != "layout_ready":
            return
        try:
            await drawing.extract_drawing_facts(task_id, target_code=target_code, target_dn=target_dn)
        except (DrawingError, VisionModelError):
            return
        except Exception as exc:
            await drawing.extraction_repository.set_status(
                task_id,
                "failed",
                100,
                "failed",
                "drawing_extraction_failed",
                str(exc),
            )


# 拒绝同时提交新旧模型上传字段，并限制模型及图纸扩展名。
def _validate_uploads(
    source_file: UploadFile | None,
    step_file: UploadFile | None,
    drawing_file: UploadFile | None,
) -> None:
    if source_file and step_file:
        raise HTTPException(
            status_code=400,
            detail={"code": "MULTIPLE_SOURCE_FILES", "message": "source_file 与旧 step_file 不能同时上传"},
        )
    if source_file:
        try:
            identify_source(source_file.filename or "")
        except IngestSourceError as exc:
            raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
    if step_file and not (step_file.filename or "").lower().endswith((".step", ".stp")):
        raise HTTPException(status_code=400, detail="only STEP/STP files are supported")
    if drawing_file and not (drawing_file.filename or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(status_code=400, detail="only PNG, JPG, JPEG, or WEBP drawings are supported")


# 保存上传并绑定模型版本；图纸只有在版本存在时建任务，否则暂存并返回等待状态。
async def _apply_source_updates(
    build_id: UUID,
    *,
    build: dict,
    component_name: str,
    source_file: UploadFile | None,
    step_file: UploadFile | None,
    drawing_file: UploadFile | None,
    build_service: ComponentBuildService,
    cad_service: CadService,
    drawing_service: DrawingLayoutService,
    settings: Settings,
) -> dict:
    drawing_path: Path | None = None
    staged_drawing_path: Path | None = None

    if drawing_file:
        drawing_path = await _save_drawing_upload(drawing_file, settings)
    elif source_file or step_file:
        staged_drawing_path = _find_pending_drawing(build_id, settings)
        if staged_drawing_path and staged_drawing_path.exists():
            staged_drawing_path.unlink()
            staged_drawing_path = None

    cad: dict | None = None
    if source_file:
        source = identify_source(source_file.filename or "")
        cad = await cad_service.create_source_from_upload(
            source_file,
            component_name,
            source_format=source.source_format,
            processing_route=source.processing_route,
        )
    elif step_file:
        cad = await cad_service.create_source_from_upload(
            step_file,
            component_name,
            source_format="STEP",
            processing_route="step_cad_parse",
        )

    if cad:
        build = await build_service.attach_step(
            build_id,
            model_id=UUID(str(cad["model_id"])),
            revision_id=UUID(str(cad["revision_id"])),
        )
        if source_file or step_file:
            schedule_ingest(UUID(str(cad["revision_id"])), settings)

    if drawing_path and build.get("cad_revision_id"):
        drawing_task = await drawing_service.create_task(
            revision_id=UUID(build["cad_revision_id"]),
            drawing_file=drawing_path,
            target_code=build["component_id"],
            target_dn=None,
        )
        build = await build_service.attach_drawing(build_id, task_id=UUID(str(drawing_task.id)))
        schedule_drawing_pipeline(
            UUID(str(drawing_task.id)),
            settings,
            target_code=build["component_id"],
            target_dn=None,
        )
        if staged_drawing_path and staged_drawing_path.exists():
            staged_drawing_path.unlink()
    elif drawing_file:
        await _stage_pending_drawing(build_id, drawing_file, settings, source_path=drawing_path)
        return await build_service.set_status(
            build_id,
            status="draft",
            message="drawing_waiting_for_step",
        )

    if source_file or step_file or drawing_file:
        response = await build_service.set_status(
            build_id,
            status="parsing_sources",
            message="sources_queued",
            error_code=None,
            error_message=None,
        )
        if (source_file or step_file) and cad:
            response.update({
                "part_id": response["id"],
                "task_id": str(cad["task_id"]),
                "source_format": cad["source_format"],
                "processing_route": cad["processing_route"],
                "source_sha256": cad["source_sha256"],
                "status": "queued",
                "current_stage": "queued",
                "progress": 0,
            })
        return response
    return await build_service.get_build(build_id)


# 按构建 UUID 隔离尚未关联模型的图纸暂存目录。
def _pending_drawing_path(build_id: UUID, settings: Settings) -> Path:
    return Path(settings.cad_spec_work_dir) / "component-build-pending" / str(build_id) / "drawing"


# 在该构建暂存目录寻找图纸文件，目录不存在返回空值。
def _find_pending_drawing(build_id: UUID, settings: Settings) -> Path | None:
    parent = _pending_drawing_path(build_id, settings).parent
    return next(parent.glob("drawing.*"), None) if parent.exists() else None


# 按上传扩展名复制图纸到构建专属暂存目录，供等待模型阶段保留原图。
async def _stage_pending_drawing(
    build_id: UUID,
    drawing_file: UploadFile,
    settings: Settings,
    *,
    source_path: Path,
) -> Path:
    suffix = Path(drawing_file.filename or "").suffix.lower()
    target = _pending_drawing_path(build_id, settings).with_suffix(suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source_path.read_bytes())
    return target


# 用随机 UUID 文件名保存图纸，避免用户文件名冲突。
async def _save_drawing_upload(drawing_file: UploadFile, settings: Settings) -> Path:
    suffix = Path(drawing_file.filename or "").suffix.lower()
    upload_dir = Path(settings.cad_spec_work_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    drawing_path = upload_dir / f"{uuid.uuid4()}{suffix}"
    drawing_path.write_bytes(await drawing_file.read())
    return drawing_path


# 将服务层构建不存在异常转换为统一 404 响应。
async def _get_build_or_404(service: ComponentBuildService, build_id: UUID) -> dict:
    try:
        return await service.get_build(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


# 保留业务错误码，并在对外消息中隐藏本地路径。
def _error_detail(exc: Exception) -> dict:
    return {
        "code": getattr(exc, "code", "component_build_upload_failed"),
        "message": redact_local_paths(str(exc)),
    }


# 仅对已创建的构建记录失败状态；状态写入自身失败时不覆盖原上传异常。
async def _mark_build_failed(service: ComponentBuildService, build_id: UUID | None, exc: Exception) -> None:
    if build_id is None:
        return
    try:
        await service.set_status(
            build_id,
            status="source_failed",
            message="source_failed",
            error_code=getattr(exc, "code", "component_build_upload_failed"),
            error_message=str(exc),
        )
    except Exception:
        return
