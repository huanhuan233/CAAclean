from __future__ import annotations

import asyncio
import hashlib
import re
import shutil
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import UploadFile

from app.cad.parser_runner import FreeCadParserError, run_freecad_parser
from app.cad.repository import CadRepository
from app.cad.result_validator import validate_parser_result
from app.core.config import Settings


SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
STRUCTURE_ENTITY_TYPES = {"root", "assembly", "part", "imported_object", "body", "solid"}


class CadService:
    def __init__(self, repository: CadRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    async def create_model_from_upload(self, file: UploadFile, name: str | None) -> dict:
        filename = Path(file.filename or "").name
        ext = Path(filename).suffix.lower()
        if ext not in {".step", ".stp"}:
            raise ValueError("only STEP/STP files are supported")

        content = await file.read()
        if not content:
            raise ValueError("empty STEP/STP file is not allowed")
        max_bytes = self.settings.cad_max_upload_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(f"file exceeds {self.settings.cad_max_upload_mb} MB limit")

        sha256 = hashlib.sha256(content).hexdigest()
        model_name = name or Path(filename).stem or "cad-model"
        safe_filename = SAFE_NAME_RE.sub("_", filename) or f"source{ext}"

        # Create DB records first so the revision UUID becomes the storage directory name.
        model, revision = await self.repository.create_upload_revision(
            name=model_name,
            source_file_name=safe_filename,
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
        await self.repository.session.commit()

        asyncio.create_task(self.parse_revision(revision.id))
        return {"model_id": model.id, "revision_id": revision.id, "status": revision.status}

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

    async def list_models(self, page: int, page_size: int) -> dict:
        rows, total = await self.repository.list_models(page, page_size)
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

    async def delete_model_files(self, revision_id: UUID) -> None:
        revision_dir = (Path(self.settings.cad_work_dir) / str(revision_id)).resolve()
        work_dir = Path(self.settings.cad_work_dir).resolve()
        if work_dir not in revision_dir.parents and revision_dir != work_dir:
            raise ValueError("unsafe CAD work directory")
        if revision_dir.exists():
            shutil.rmtree(revision_dir)
