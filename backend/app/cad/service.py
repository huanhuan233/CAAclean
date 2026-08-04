from __future__ import annotations

import asyncio
import hashlib
import shutil
from pathlib import Path
from typing import Callable
from uuid import UUID

import aiofiles
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.cad.parser_runner import FreeCadParserError, run_freecad_parser
from app.cad.repository import CadRepository
from app.cad.result_validator import validate_parser_result
from app.core.config import Settings
from app.db.session import SessionLocal
from app.measurement.repository import MeasurementRepository
from app.measurement.service import MeasurementService


STRUCTURE_ENTITY_TYPES = {"root", "assembly", "part", "imported_object", "body", "solid"}
_SEMAPHORES: dict[int, asyncio.Semaphore] = {}


def _semaphore_for(limit: int) -> asyncio.Semaphore:
    safe_limit = max(1, int(limit))
    if safe_limit not in _SEMAPHORES:
        _SEMAPHORES[safe_limit] = asyncio.Semaphore(safe_limit)
    return _SEMAPHORES[safe_limit]


class CadService:
    def __init__(
        self,
        repository: CadRepository,
        settings: Settings,
        *,
        session_factory: Callable[[], object] = SessionLocal,
        repository_factory: Callable[[AsyncSession], CadRepository] = CadRepository,
        concurrency_limiter: asyncio.Semaphore | None = None,
    ):
        self.repository = repository
        self.settings = settings
        self.session_factory = session_factory
        self.repository_factory = repository_factory
        self.concurrency_limiter = concurrency_limiter or _semaphore_for(settings.cad_max_concurrency)

    async def create_model_from_upload(self, file: UploadFile, name: str | None) -> dict:
        filename = Path(file.filename or "").name
        ext = Path(filename).suffix.lower()
        if ext not in {".step", ".stp"}:
            raise ValueError("only STEP/STP files are supported")

        result = await self.create_source_from_upload(
            file,
            name,
            source_format="STEP",
            processing_route="step_cad_parse",
        )
        asyncio.create_task(self.parse_revision_in_background(result["revision_id"]))
        return result

    async def create_source_from_upload(
        self,
        file: UploadFile,
        name: str | None,
        *,
        source_format: str,
        processing_route: str,
    ) -> dict:
        """用途：安全保存统一源模型并建立持久 Revision；具体解析由上层编排器调度。"""
        filename = Path(file.filename or "").name
        ext = Path(filename).suffix.lower()
        allowed = {
            "STEP": {".step", ".stp"},
            "CATPART": {".catpart"},
        }
        if source_format not in allowed or ext not in allowed[source_format]:
            raise ValueError("source format does not match file extension")

        content = await file.read()
        if not content:
            raise ValueError("empty source model file is not allowed")
        max_bytes = self.settings.cad_max_upload_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(f"file exceeds {self.settings.cad_max_upload_mb} MB limit")

        sha256 = hashlib.sha256(content).hexdigest()
        model_name = name or Path(filename).stem or "cad-model"

        # 用途：先创建记录取得 Revision UUID，再把文件放进该 UUID 的隔离目录。
        model, revision = await self.repository.create_upload_revision(
            name=model_name,
            source_file_name=filename,
            source_file_ext=ext,
            source_file_path="pending",
            source_file_size=len(content),
            source_sha256=sha256,
        )

        revision_dir = Path(self.settings.cad_work_dir) / str(revision.id)
        revision_dir.mkdir(parents=True, exist_ok=True)
        source_path = revision_dir / f"source{ext}"
        async with aiofiles.open(source_path, "wb") as out:
            await out.write(content)
        revision.source_file_path = str(source_path)
        commit = getattr(self.repository.session, "commit", None)
        if commit:
            await commit()
        update_manifest = getattr(self.repository, "update_revision_manifest", None)
        if update_manifest:
            await update_manifest(
                revision.id,
                {
                    "ingest": {
                        "source_format": source_format,
                        "processing_route": processing_route,
                        "source_file_name": filename,
                        "source_sha256": sha256,
                    }
                },
            )
        return {
            "model_id": model.id,
            "revision_id": revision.id,
            "task_id": revision.id,
            "status": revision.status,
            "source_format": source_format,
            "processing_route": processing_route,
            "source_sha256": sha256,
        }

    async def parse_revision_in_background(self, revision_id: UUID) -> None:
        async with self.session_factory() as session:
            service = CadService(
                self.repository_factory(session),
                self.settings,
                session_factory=self.session_factory,
                repository_factory=self.repository_factory,
                concurrency_limiter=self.concurrency_limiter,
            )
            await service.parse_revision(revision_id)

    async def parse_revision(self, revision_id: UUID) -> None:
        revision = await self.repository.get_revision(revision_id)
        if revision is None:
            return
        await self.repository.set_revision_status(
            revision_id,
            status="processing",
            progress=10,
            status_message="running_freecad",
        )
        try:
            async with self.concurrency_limiter:
                result_data = await run_freecad_parser(
                    Path(revision.source_file_path),
                    revision_id,
                    Path(self.settings.cad_work_dir) / str(revision_id),
                    self.settings,
                )
            result = validate_parser_result(result_data)
            await self.repository.persist_parser_result(revision_id, result)
        except (FreeCadParserError, ValueError) as exc:
            await self.repository.set_revision_status(
                revision_id,
                status="failed",
                progress=100,
                status_message="failed",
                error_code="parse_failed",
                error_message=str(exc)[:1000],
            )

    async def get_revision_status(self, revision_id: UUID) -> dict:
        revision = await self.repository.get_revision(revision_id)
        if revision is None:
            raise LookupError("revision not found")
        return {
            "status": revision.status,
            "progress": revision.progress,
            "status_message": revision.status_message,
            "error_code": revision.error_code,
            "error_message": revision.error_message,
        }

    async def list_models(self, page: int, page_size: int, has_build: bool = False) -> dict:
        rows, total = await self.repository.list_models(page, page_size, has_build=has_build)
        items = []
        for model, revision in rows:
            items.append(
                {
                    "id": model.id,
                    "name": model.name,
                    "current_revision_id": model.current_revision_id,
                    "status": revision.status if revision else None,
                    "progress": revision.progress if revision else None,
                    "face_count": revision.face_count if revision else 0,
                    "edge_count": revision.edge_count if revision else 0,
                    "vertex_count": revision.vertex_count if revision else 0,
                    "created_at": model.created_at.isoformat(),
                }
            )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_revision_tree(self, revision_id: UUID) -> list[dict]:
        entities = await self.repository.list_entities(revision_id)
        return self._build_tree(entities)

    async def get_structure_tree(self, revision_id: UUID) -> list[dict]:
        entities = [entity for entity in await self.repository.list_entities(revision_id) if entity.entity_type in STRUCTURE_ENTITY_TYPES]
        return self._build_tree(entities)

    async def list_revision_entities(
        self,
        revision_id: UUID,
        *,
        parent_entity_id: UUID | None = None,
        entity_type: str | None = None,
        geometry_type: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        rows, total = await self.repository.list_entities_filtered(
            revision_id,
            parent_entity_id=parent_entity_id,
            entity_type=entity_type,
            geometry_type=geometry_type,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._entity_to_dict(entity) for entity in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_revision_entity(self, revision_id: UUID, entity_id: UUID) -> dict:
        entity = await self.repository.get_entity(entity_id)
        if entity is None or entity.revision_id != revision_id:
            raise LookupError("entity not found")
        return self._entity_to_dict(entity)

    async def list_revision_meshes(
        self,
        revision_id: UUID,
        *,
        entity_id: UUID | None = None,
        parent_entity_id: UUID | None = None,
        page: int = 1,
        page_size: int = 1000,
    ) -> dict:
        rows, total = await self.repository.list_meshes_filtered(
            revision_id,
            entity_id=entity_id,
            parent_entity_id=parent_entity_id,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._mesh_to_dict(mesh) for mesh in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_face_topology(self, revision_id: UUID, face_id: UUID) -> dict:
        edges = await self.repository.get_related_entities(revision_id, face_id, "bounded_by_edge")
        adjacent_faces = await self.repository.get_related_entities(revision_id, face_id, "adjacent_to")
        if not edges:
            edges = await self.repository.list_child_entities(revision_id, face_id, "edge")
        return {
            "edges": [self._entity_to_dict(entity) for entity in edges],
            "adjacent_faces": [self._entity_to_dict(entity) for entity in adjacent_faces],
        }

    async def get_edge_topology(self, revision_id: UUID, edge_id: UUID) -> dict:
        vertices = await self.repository.get_related_entities(revision_id, edge_id, "has_vertex")
        faces = await self.repository.get_source_entities_for_target(revision_id, edge_id, "bounded_by_edge")
        if not vertices:
            vertices = await self.repository.list_child_entities(revision_id, edge_id, "vertex")
        if not faces:
            edge = await self.repository.get_entity(edge_id)
            if edge and edge.parent_entity_id:
                parent = await self.repository.get_entity(edge.parent_entity_id)
                if parent and parent.revision_id == revision_id and parent.entity_type == "face":
                    faces = [parent]
        return {
            "vertices": [self._entity_to_dict(entity) for entity in vertices],
            "faces": [self._entity_to_dict(entity) for entity in faces],
        }

    async def list_revision_measurements(
        self,
        revision_id: UUID,
        *,
        measurement_type: str | None = None,
        scope_entity_id: UUID | None = None,
        confidence_min: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        rows, total = await MeasurementRepository(self.repository.session).list_measurements(
            revision_id,
            measurement_type=measurement_type,
            scope_entity_id=scope_entity_id,
            confidence_min=confidence_min,
            page=page,
            page_size=page_size,
        )
        return {"items": [self._measurement_to_dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    async def get_revision_measurement(self, revision_id: UUID, measurement_id: UUID) -> dict:
        measurement = await MeasurementRepository(self.repository.session).get_measurement(measurement_id)
        if measurement is None or measurement.revision_id != revision_id:
            raise LookupError("measurement not found")
        return self._measurement_to_dict(measurement)

    async def list_revision_features(
        self,
        revision_id: UUID,
        *,
        feature_type: str | None = None,
        scope_entity_id: UUID | None = None,
        confidence_min: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        rows, total = await MeasurementRepository(self.repository.session).list_features(
            revision_id,
            feature_type=feature_type,
            scope_entity_id=scope_entity_id,
            confidence_min=confidence_min,
            page=page,
            page_size=page_size,
        )
        return {"items": [self._feature_to_dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    async def get_revision_feature(self, revision_id: UUID, feature_id: UUID) -> dict:
        feature = await MeasurementRepository(self.repository.session).get_feature(feature_id)
        if feature is None or feature.revision_id != revision_id:
            raise LookupError("feature not found")
        return self._feature_to_dict(feature)

    async def recompute_revision_measurements(self, revision_id: UUID) -> dict:
        return await MeasurementService(MeasurementRepository(self.repository.session)).recompute_revision(revision_id)

    def _build_tree(self, entities) -> list[dict]:
        nodes: dict[UUID, dict] = {}
        roots: list[dict] = []
        for entity in entities:
            label = entity.label or entity.name or entity.source_ref or entity.entity_type
            nodes[entity.id] = {
                "id": entity.id,
                "parent_entity_id": entity.parent_entity_id,
                "entity_type": entity.entity_type,
                "label": label,
                "source_ref": entity.source_ref,
                "geometry_type": entity.geometry_type,
                "placement": entity.placement,
                "volume": entity.volume,
                "bounding_box": entity.bounding_box,
                "metadata": entity.metadata_json,
                "children": [],
            }
        for entity in entities:
            node = nodes[entity.id]
            if entity.parent_entity_id and entity.parent_entity_id in nodes:
                nodes[entity.parent_entity_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    def _entity_to_dict(self, entity) -> dict:
        return {
            "id": entity.id,
            "revision_id": entity.revision_id,
            "parent_entity_id": entity.parent_entity_id,
            "entity_type": entity.entity_type,
            "source_ref": entity.source_ref,
            "source_index": entity.source_index,
            "name": entity.name,
            "label": entity.label,
            "tree_path": entity.tree_path,
            "sort_order": entity.sort_order,
            "geometry_type": entity.geometry_type,
            "area": entity.area,
            "volume": entity.volume,
            "length": entity.length,
            "center": entity.center,
            "bounding_box": entity.bounding_box,
            "placement": entity.placement,
            "geometry": entity.geometry,
            "metadata": entity.metadata_json,
        }

    def _mesh_to_dict(self, mesh) -> dict:
        return {
            "id": mesh.id,
            "revision_id": mesh.revision_id,
            "entity_id": mesh.entity_id,
            "mesh_type": mesh.mesh_type,
            "positions": mesh.positions,
            "indices": mesh.indices,
            "normals": mesh.normals,
            "color": mesh.color,
            "linear_deflection": mesh.linear_deflection,
            "angular_deflection": mesh.angular_deflection,
            "vertex_count": mesh.vertex_count,
            "triangle_count": mesh.triangle_count,
        }

    def _measurement_to_dict(self, measurement) -> dict:
        return {
            "id": measurement.id,
            "revision_id": measurement.revision_id,
            "scope_entity_id": measurement.scope_entity_id,
            "feature_id": measurement.feature_id,
            "measurement_type": measurement.measurement_type,
            "raw_value": measurement.raw_value,
            "normalized_value": measurement.normalized_value,
            "unit": measurement.unit,
            "source_entity_ids": measurement.source_entity_ids,
            "method": measurement.method,
            "confidence": measurement.confidence,
            "algorithm_version": measurement.algorithm_version,
            "metadata": measurement.metadata_json,
            "created_at": measurement.created_at.isoformat(),
        }

    def _feature_to_dict(self, feature) -> dict:
        return {
            "id": feature.id,
            "revision_id": feature.revision_id,
            "scope_entity_id": feature.scope_entity_id,
            "feature_type": feature.feature_type,
            "source_entity_ids": feature.source_entity_ids,
            "parameters": feature.parameters,
            "axis": feature.axis,
            "center": feature.center,
            "confidence": feature.confidence,
            "algorithm": feature.algorithm,
            "algorithm_version": feature.algorithm_version,
            "status": feature.status,
            "metadata": feature.metadata_json,
            "created_at": feature.created_at.isoformat(),
            "updated_at": feature.updated_at.isoformat(),
        }

    async def delete_model_files(self, revision_id: UUID) -> None:
        revision_dir = (Path(self.settings.cad_work_dir) / str(revision_id)).resolve()
        work_dir = Path(self.settings.cad_work_dir).resolve()
        if work_dir not in revision_dir.parents and revision_dir != work_dir:
            raise ValueError("unsafe CAD work directory")
        if revision_dir.exists():
            shutil.rmtree(revision_dir)


async def recover_interrupted_revisions(
    settings: Settings,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    repository_factory: Callable[[AsyncSession], CadRepository] = CadRepository,
) -> int:
    async with session_factory() as session:
        repository = repository_factory(session)
        return await repository.fail_interrupted_revisions(
            settings.cad_stale_job_minutes,
            "interrupted_by_service_restart",
        )
