from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.drawing.providers import AutoLayoutProvider, ManualLayoutProvider, MineruLayoutProvider, VisionLayoutProvider
from app.drawing.repository import SqlAlchemyDrawingRepository
from app.drawing.schemas import DrawingError, DrawingLayoutStatusOut, DrawingRegionListOut, DrawingTaskOut, ManualRegionsIn
from app.drawing.service import DrawingLayoutService


router = APIRouter(prefix="/api/cad/spec", tags=["cad-spec"])


def build_layout_provider(settings: Settings):
    mineru = MineruLayoutProvider(
        mode=settings.mineru_layout_mode,
        url=settings.mineru_layout_url or None,
        command=settings.mineru_layout_command or None,
        timeout=settings.mineru_layout_timeout,
    )
    vision = VisionLayoutProvider()
    if settings.drawing_layout_provider == "mineru":
        return mineru
    if settings.drawing_layout_provider == "vision":
        return vision
    if settings.drawing_layout_provider == "manual":
        return ManualLayoutProvider([])
    return AutoLayoutProvider(mineru=mineru, vision=vision)


def get_drawing_service(session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> DrawingLayoutService:
    return DrawingLayoutService(
        SqlAlchemyDrawingRepository(session),
        work_dir=Path(settings.cad_spec_work_dir),
        provider=build_layout_provider(settings),
        max_image_mb=settings.drawing_max_image_mb,
        max_side=settings.drawing_max_side,
        inference_max_side=settings.drawing_inference_max_side,
        crop_padding={
            "product_information": settings.drawing_crop_padding_ratio,
            "dimension_diagram": settings.drawing_diagram_padding_ratio,
            "parameter_table": settings.drawing_table_padding_ratio,
        },
        merge_gap_ratio=settings.drawing_region_merge_gap_ratio,
    )


@router.post("/tasks", response_model=DrawingTaskOut, status_code=status.HTTP_202_ACCEPTED)
async def create_spec_task(
    revision_id: uuid.UUID = Form(...),
    target_code: str | None = Form(default=None),
    target_dn: str | None = Form(default=None),
    drawing_file: UploadFile = File(...),
    service: DrawingLayoutService = Depends(get_drawing_service),
):
    try:
        suffix = Path(drawing_file.filename or "").suffix.lower()
        temp_dir = Path(service.work_dir) / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"{uuid.uuid4()}{suffix}"
        temp_path.write_bytes(await drawing_file.read())
        task = await service.create_task(revision_id=revision_id, drawing_file=temp_path, target_code=target_code, target_dn=target_dn)
        return {"task_id": task.id, "revision_id": task.revision_id, "status": task.status}
    except DrawingError as exc:
        raise _http_error(exc) from exc


@router.post("/tasks/{task_id}/layout", status_code=status.HTTP_202_ACCEPTED)
async def start_layout(task_id: uuid.UUID, service: DrawingLayoutService = Depends(get_drawing_service)):
    try:
        return await service.start_layout(task_id)
    except DrawingError as exc:
        raise _http_error(exc) from exc


@router.get("/tasks/{task_id}/layout/status", response_model=DrawingLayoutStatusOut)
async def layout_status(task_id: uuid.UUID, service: DrawingLayoutService = Depends(get_drawing_service)):
    try:
        return await service.get_layout_status(task_id)
    except DrawingError as exc:
        raise _http_error(exc) from exc


@router.get("/tasks/{task_id}/regions", response_model=DrawingRegionListOut)
async def list_regions(task_id: uuid.UUID, service: DrawingLayoutService = Depends(get_drawing_service)):
    try:
        items = await service.list_regions(task_id)
        return {"items": items, "total": len(items)}
    except DrawingError as exc:
        raise _http_error(exc) from exc


@router.get("/tasks/{task_id}/regions/{region_id}/image")
async def region_image(task_id: uuid.UUID, region_id: uuid.UUID, service: DrawingLayoutService = Depends(get_drawing_service)):
    regions = await service.repository.list_active_regions(task_id)
    region = next((item for item in regions if item.id == region_id), None)
    if region is None or not region.crop_file_path:
        raise HTTPException(status_code=404, detail="region image not found")
    return FileResponse(region.crop_file_path, media_type="image/png", filename=region.crop_file_name)


@router.get("/tasks/{task_id}/drawing/image")
async def drawing_image(
    task_id: uuid.UUID,
    variant: str = Query(default="original", pattern="^(original|inference)$"),
    service: DrawingLayoutService = Depends(get_drawing_service),
):
    source = await service.repository.get_source_for_task(task_id)
    if source is None:
        raise HTTPException(status_code=404, detail="drawing source not found")
    if variant == "original":
        return FileResponse(source.file_path, media_type=source.mime_type, filename=source.file_name)
    path = Path(service.work_dir) / str(task_id) / "whole_inference.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="inference image not found")
    return FileResponse(path, media_type="image/png", filename="whole_inference.png")


@router.put("/tasks/{task_id}/regions")
async def put_regions(task_id: uuid.UUID, payload: ManualRegionsIn, service: DrawingLayoutService = Depends(get_drawing_service)):
    try:
        return await service.apply_manual_regions(task_id, payload.regions)
    except DrawingError as exc:
        raise _http_error(exc) from exc


def _http_error(exc: DrawingError) -> HTTPException:
    status_code = 400
    if exc.code in {"manual_layout_required"}:
        status_code = 409
    return HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message})
