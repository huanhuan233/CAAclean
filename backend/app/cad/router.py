from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cad.repository import CadRepository
from app.cad.schemas import CadEntityOut, CadPagedResult, CadParseStatus, CadTopologyResult, CadTreeNode, CadUploadResponse
from app.cad.service import CadService
from app.core.config import Settings, get_settings
from app.db.session import get_session


router = APIRouter(prefix="/api/cad", tags=["cad"])


def get_cad_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> CadService:
    return CadService(CadRepository(session), settings)


@router.post("/models", response_model=CadUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_model(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    service: CadService = Depends(get_cad_service),
) -> dict:
    filename = file.filename or ""
    if not filename.lower().endswith((".step", ".stp")):
        raise HTTPException(status_code=400, detail="only STEP/STP files are supported")
    try:
        return await service.create_model_from_upload(file, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models", response_model=CadPagedResult)
async def list_models(
    page: int = 1,
    page_size: int = 20,
    has_build: bool = False,
    service: CadService = Depends(get_cad_service),
) -> dict:
    return await service.list_models(page, page_size, has_build=has_build)


@router.get("/revisions/{revision_id}/status", response_model=CadParseStatus)
async def revision_status(revision_id: UUID, service: CadService = Depends(get_cad_service)) -> dict:
    try:
        return await service.get_revision_status(revision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="revision not found") from exc


@router.get("/revisions/{revision_id}/tree", response_model=list[CadTreeNode])
async def revision_tree(revision_id: UUID, service: CadService = Depends(get_cad_service)) -> list[dict]:
    return await service.get_revision_tree(revision_id)


@router.get("/revisions/{revision_id}/structure-tree", response_model=list[CadTreeNode])
async def revision_structure_tree(revision_id: UUID, service: CadService = Depends(get_cad_service)) -> list[dict]:
    return await service.get_structure_tree(revision_id)


@router.get("/revisions/{revision_id}/entities", response_model=CadPagedResult)
async def revision_entities(
    revision_id: UUID,
    parent_entity_id: UUID | None = None,
    entity_type: str | None = None,
    geometry_type: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    service: CadService = Depends(get_cad_service),
) -> dict:
    return await service.list_revision_entities(
        revision_id,
        parent_entity_id=parent_entity_id,
        entity_type=entity_type,
        geometry_type=geometry_type,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


@router.get("/revisions/{revision_id}/entities/{entity_id}", response_model=CadEntityOut)
async def revision_entity(revision_id: UUID, entity_id: UUID, service: CadService = Depends(get_cad_service)) -> dict:
    try:
        return await service.get_revision_entity(revision_id, entity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="entity not found") from exc


@router.get("/revisions/{revision_id}/meshes", response_model=CadPagedResult)
async def revision_meshes(
    revision_id: UUID,
    entity_id: UUID | None = None,
    parent_entity_id: UUID | None = None,
    page: int = 1,
    page_size: int = 1000,
    service: CadService = Depends(get_cad_service),
) -> dict:
    return await service.list_revision_meshes(
        revision_id,
        entity_id=entity_id,
        parent_entity_id=parent_entity_id,
        page=page,
        page_size=page_size,
    )


@router.get("/revisions/{revision_id}/faces/{face_id}/topology", response_model=CadTopologyResult)
async def face_topology(revision_id: UUID, face_id: UUID, service: CadService = Depends(get_cad_service)) -> dict:
    return await service.get_face_topology(revision_id, face_id)


@router.get("/revisions/{revision_id}/edges/{edge_id}/topology", response_model=CadTopologyResult)
async def edge_topology(revision_id: UUID, edge_id: UUID, service: CadService = Depends(get_cad_service)) -> dict:
    return await service.get_edge_topology(revision_id, edge_id)


@router.get("/revisions/{revision_id}/measurements", response_model=CadPagedResult)
async def revision_measurements(
    revision_id: UUID,
    measurement_type: str | None = None,
    scope_entity_id: UUID | None = None,
    confidence_min: float | None = None,
    page: int = 1,
    page_size: int = 20,
    service: CadService = Depends(get_cad_service),
) -> dict:
    return await service.list_revision_measurements(
        revision_id,
        measurement_type=measurement_type,
        scope_entity_id=scope_entity_id,
        confidence_min=confidence_min,
        page=page,
        page_size=page_size,
    )


@router.post("/revisions/{revision_id}/measurements/recompute")
async def recompute_revision_measurements(revision_id: UUID, service: CadService = Depends(get_cad_service)) -> dict:
    return await service.recompute_revision_measurements(revision_id)


@router.get("/revisions/{revision_id}/measurements/{measurement_id}")
async def revision_measurement(revision_id: UUID, measurement_id: UUID, service: CadService = Depends(get_cad_service)) -> dict:
    try:
        return await service.get_revision_measurement(revision_id, measurement_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="measurement not found") from exc


@router.get("/revisions/{revision_id}/features", response_model=CadPagedResult)
async def revision_features(
    revision_id: UUID,
    feature_type: str | None = None,
    scope_entity_id: UUID | None = None,
    confidence_min: float | None = None,
    page: int = 1,
    page_size: int = 20,
    service: CadService = Depends(get_cad_service),
) -> dict:
    return await service.list_revision_features(
        revision_id,
        feature_type=feature_type,
        scope_entity_id=scope_entity_id,
        confidence_min=confidence_min,
        page=page,
        page_size=page_size,
    )


@router.get("/revisions/{revision_id}/features/{feature_id}")
async def revision_feature(revision_id: UUID, feature_id: UUID, service: CadService = Depends(get_cad_service)) -> dict:
    try:
        return await service.get_revision_feature(revision_id, feature_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="feature not found") from exc


@router.post("/revisions/{revision_id}/exports/v2")
async def export_v2(revision_id: UUID) -> None:
    raise HTTPException(
        status_code=501,
        detail={
            "code": "v2_integration_not_implemented",
            "message": "V2 integration is reserved for a later phase.",
        },
    )
