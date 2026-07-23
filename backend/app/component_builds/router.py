from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cad.router import get_cad_service
from app.cad.service import CadService
from app.component_builds.catalog import catalog_payload
from app.component_builds.repository import SqlAlchemyComponentBuildRepository
from app.component_builds.schemas import ComponentBuildRetryIn
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
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_component_build(
    category_code: str = Form(...),
    part_type_code: str = Form(...),
    component_name: str = Form(...),
    standard_number: str | None = Form(default=None),
    version: str = Form(default="1.0.0"),
    step_file: UploadFile | None = File(default=None),
    drawing_file: UploadFile | None = File(default=None),
    build_service: ComponentBuildService = Depends(get_component_build_service),
    cad_service: CadService = Depends(get_cad_service),
    drawing_service: DrawingLayoutService = Depends(get_drawing_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    _validate_uploads(step_file, drawing_file)
    build_id: UUID | None = None
    try:
        build = await build_service.create_catalog_build(
            category_code=category_code,
            part_type_code=part_type_code,
            component_name=component_name,
            standard_number=standard_number,
            version=version,
            status="uploading" if step_file else "draft",
        )
        build_id = UUID(str(build["id"]))
        return await _apply_source_updates(
            build_id,
            build=build,
            component_name=component_name,
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
    step_file: UploadFile | None = File(default=None),
    drawing_file: UploadFile | None = File(default=None),
    build_service: ComponentBuildService = Depends(get_component_build_service),
    cad_service: CadService = Depends(get_cad_service),
    drawing_service: DrawingLayoutService = Depends(get_drawing_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    _validate_uploads(step_file, drawing_file)
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


@router.get("/{build_id}/status")
async def component_build_status(build_id: UUID, service: ComponentBuildService = Depends(get_component_build_service)) -> dict:
    try:
        return await service.get_status(build_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "component_build_not_found", "message": str(exc)}) from exc


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


def _validate_uploads(step_file: UploadFile | None, drawing_file: UploadFile | None) -> None:
    if step_file and not (step_file.filename or "").lower().endswith((".step", ".stp")):
        raise HTTPException(status_code=400, detail="only STEP/STP files are supported")
    if drawing_file and not (drawing_file.filename or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(status_code=400, detail="only PNG, JPG, JPEG, or WEBP drawings are supported")


async def _apply_source_updates(
    build_id: UUID,
    *,
    build: dict,
    component_name: str,
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
    elif step_file:
        staged_drawing_path = _find_pending_drawing(build_id, settings)
        drawing_path = staged_drawing_path
        if drawing_path is None and build.get("drawing_task_id"):
            drawing_path = await _existing_drawing_path(drawing_service, UUID(build["drawing_task_id"]))

    if step_file:
        cad = await cad_service.create_model_from_upload(step_file, component_name)
        build = await build_service.attach_step(
            build_id,
            model_id=UUID(str(cad["model_id"])),
            revision_id=UUID(str(cad["revision_id"])),
        )

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

    if step_file or drawing_file:
        return await build_service.set_status(
            build_id,
            status="parsing_sources",
            message="sources_queued",
            error_code=None,
            error_message=None,
        )
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


async def _existing_drawing_path(drawing_service: DrawingLayoutService, task_id: UUID) -> Path | None:
    repository = getattr(drawing_service, "repository", None)
    if repository is None:
        return None
    source = await repository.get_source_for_task(task_id)
    return Path(source.file_path) if source else None


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
    return {"code": getattr(exc, "code", "component_build_upload_failed"), "message": str(exc)}


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
