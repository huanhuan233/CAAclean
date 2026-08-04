from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
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


def get_component_build_service(session: AsyncSession = Depends(get_session)) -> ComponentBuildService:
    return ComponentBuildService(
        SqlAlchemyComponentBuildRepository(session),
        source_status_reader=SqlAlchemySourceStatusReader(session),
        fusion_source_reader=SqlAlchemyFusionSourceReader(session),
    )


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


@router.get("/tree")
async def component_build_tree(service: ComponentBuildService = Depends(get_component_build_service)) -> list[dict]:
    return await service.get_tree()


@router.get("/catalog")
async def component_build_catalog() -> dict:
    return catalog_payload()


@router.get("/{build_id}")
async def component_build(build_id: UUID, service: ComponentBuildService = Depends(get_component_build_service)) -> dict:
    return await _get_build_or_404(service, build_id)


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


@router.get("/{build_id}/status")
async def component_build_status(build_id: UUID, service: ComponentBuildService = Depends(get_component_build_service)) -> dict:
    try:
        return await service.get_status(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


@router.get("/{build_id}/viewer")
async def component_build_viewer(
    build_id: UUID,
    service: ComponentBuildService = Depends(get_component_build_service),
) -> dict:
    try:
        return await service.get_viewer_contract(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "viewer_not_found", "message": str(exc)}) from exc


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


@router.get("/{build_id}/component-spec")
async def component_spec_draft(build_id: UUID, service: ComponentBuildService = Depends(get_component_build_service)) -> dict:
    try:
        return await service.get_component_spec(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


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


@router.post("/{build_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_component_build(
    build_id: UUID,
    payload: ComponentBuildRetryIn,
    service: ComponentBuildService = Depends(get_component_build_service),
    cad_service: CadService = Depends(get_cad_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    build = await _get_build_or_404(service, build_id)
    if payload.role == "reference_step":
        if build["cad_revision_id"] is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "step_source_unavailable", "message": "STEP source is not attached"},
            )
        if build.get("processing_route") in {"step_cad_parse", "catia_feature_center"}:
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


def schedule_step_pipeline(revision_id: UUID, cad_service: CadService) -> None:
    asyncio.create_task(cad_service.parse_revision_in_background(revision_id))


def schedule_drawing_pipeline(
    task_id: UUID,
    settings: Settings,
    *,
    target_code: str | None,
    target_dn: int | None,
) -> None:
    asyncio.create_task(run_drawing_pipeline(task_id, settings, target_code=target_code, target_dn=target_dn))


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


def _pending_drawing_path(build_id: UUID, settings: Settings) -> Path:
    return Path(settings.cad_spec_work_dir) / "component-build-pending" / str(build_id) / "drawing"


def _find_pending_drawing(build_id: UUID, settings: Settings) -> Path | None:
    parent = _pending_drawing_path(build_id, settings).parent
    return next(parent.glob("drawing.*"), None) if parent.exists() else None


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


async def _save_drawing_upload(drawing_file: UploadFile, settings: Settings) -> Path:
    suffix = Path(drawing_file.filename or "").suffix.lower()
    upload_dir = Path(settings.cad_spec_work_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    drawing_path = upload_dir / f"{uuid.uuid4()}{suffix}"
    drawing_path.write_bytes(await drawing_file.read())
    return drawing_path


async def _get_build_or_404(service: ComponentBuildService, build_id: UUID) -> dict:
    try:
        return await service.get_build(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


def _error_detail(exc: Exception) -> dict:
    return {
        "code": getattr(exc, "code", "component_build_upload_failed"),
        "message": redact_local_paths(str(exc)),
    }


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
