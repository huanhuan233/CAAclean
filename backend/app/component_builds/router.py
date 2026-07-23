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
    step_file: UploadFile = File(...),
    drawing_file: UploadFile = File(...),
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
            status="uploading",
        )
        build_id = UUID(str(build["id"]))
        cad = await cad_service.create_model_from_upload(step_file, component_name)
        await build_service.attach_step(
            build_id,
            model_id=UUID(str(cad["model_id"])),
            revision_id=UUID(str(cad["revision_id"])),
        )
        drawing_path = await _save_drawing_upload(drawing_file, settings)
        drawing_task = await drawing_service.create_task(
            revision_id=UUID(str(cad["revision_id"])),
            drawing_file=drawing_path,
            target_code=build["component_id"],
            target_dn=None,
        )
        await build_service.attach_drawing(build_id, task_id=UUID(str(drawing_task.id)))
        result = await build_service.set_status(build_id, status="parsing_sources", message="sources_queued")
        schedule_drawing_pipeline(
            UUID(str(drawing_task.id)),
            settings,
            target_code=build["component_id"],
            target_dn=None,
        )
        return result
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
    settings: Settings = Depends(get_settings),
) -> dict:
    build = await _get_build_or_404(service, build_id)
    if payload.role == "reference_step":
        raise HTTPException(
            status_code=409,
            detail={"code": "step_reupload_required", "message": "re-upload STEP to retry its source parse"},
        )
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


def _validate_uploads(step_file: UploadFile, drawing_file: UploadFile) -> None:
    if not (step_file.filename or "").lower().endswith((".step", ".stp")):
        raise HTTPException(status_code=400, detail="only STEP/STP files are supported")
    if not (drawing_file.filename or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(status_code=400, detail="only PNG, JPG, JPEG, or WEBP drawings are supported")


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
