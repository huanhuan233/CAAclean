from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.component_builds.catalog import CATEGORIES, CatalogCategory, CatalogPart, find_part_by_legacy_type, find_part_by_node_id, resolve_part
from app.component_builds.component_spec import component_spec_template
from app.component_builds.fusion import FusionSourceUnavailable, fuse_component_spec
from app.db.models import CadModelRevision, CadSpecTask, ComponentBuild


INPUTS_LABEL = "\u8f93\u5165\u8d44\u6599"
DATA_FUSION_LABEL = "\u6570\u636e\u878d\u5408"
PUBLISH_VALIDATION_LABEL = "\u53d1\u5e03\u6821\u9a8c"
FUTURE_STATUS_LABEL = "\u540e\u7eed\u80fd\u529b"


class SqlAlchemySourceStatusReader:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_step_status(self, revision_id: UUID) -> dict:
        revision = await self.session.get(CadModelRevision, revision_id)
        return self._source_status(revision) if revision else {"status": "missing"}

    async def get_drawing_status(self, task_id: UUID) -> dict:
        task = await self.session.get(CadSpecTask, task_id)
        return self._source_status(task) if task else {"status": "missing"}

    @staticmethod
    def _source_status(source) -> dict:
        return {
            "status": source.status,
            "progress": source.progress,
            "status_message": getattr(source, "status_message", None),
            "error_code": getattr(source, "error_code", None),
            "error_message": getattr(source, "error_message", None),
        }


class ComponentBuildService:
    def __init__(self, repository, *, source_status_reader, fusion_source_reader=None):
        self.repository = repository
        self.source_status_reader = source_status_reader
        self.fusion_source_reader = fusion_source_reader

    async def get_tree(self) -> list[dict]:
        builds = await self.repository.list_builds()
        grouped: dict[str, dict[str, list[ComponentBuild]]] = {}
        uncategorized: list[ComponentBuild] = []
        for build in builds:
            catalog = self._catalog_for_build(build)
            if catalog is None:
                uncategorized.append(build)
                continue
            category, part = catalog
            grouped.setdefault(category.code, {}).setdefault(part.code, []).append(build)

        tree = [
            await self._category_node(category, grouped.get(category.code, {}))
            for category in CATEGORIES
        ]
        if uncategorized:
            tree.append(await self._uncategorized_node(uncategorized))
        return tree

    async def create_build(self, **fields) -> dict:
        build = await self.repository.create_build(**fields)
        return self._build_payload(build)

    async def get_component_spec(self, build_id: UUID) -> dict:
        draft = await self.repository.get_component_spec(build_id)
        return {
            "build_id": str(build_id),
            "schema": component_spec_template.schema,
            "data": draft.data if draft else component_spec_template.blank_data(),
            "saved": draft is not None,
            "updated_at": draft.updated_at.isoformat() if draft else None,
        }

    async def save_component_spec(self, build_id: UUID, data: dict) -> dict:
        normalized = component_spec_template.normalize(data)
        draft = await self.repository.save_component_spec(build_id, normalized)
        return {
            "build_id": str(build_id),
            "schema": component_spec_template.schema,
            "data": draft.data,
            "saved": True,
            "updated_at": draft.updated_at.isoformat(),
        }

    async def preview_component_spec(self, build_id: UUID, data: dict) -> str:
        await self.repository.get_build(build_id) or self._raise_missing_build(build_id)
        return component_spec_template.render_yaml(data)

    async def fuse_component_spec(self, build_id: UUID, *, overwrite: bool = False) -> dict:
        build = await self._require_build(build_id)
        if self.fusion_source_reader is None:
            raise FusionSourceUnavailable("no_sources_available")
        sources = await self.fusion_source_reader.read(build)
        if not sources.available:
            raise FusionSourceUnavailable("no_sources_available")
        current_draft = await self.repository.get_component_spec(build_id)
        current = current_draft.data if current_draft else component_spec_template.blank_data()
        result = fuse_component_spec(
            build=self._build_payload(build),
            current=current,
            sources=sources,
            overwrite=overwrite,
        )
        normalized = component_spec_template.normalize(result.data)
        draft = await self.repository.save_component_spec(build_id, normalized)
        return {
            "build_id": str(build_id),
            "status": "completed",
            "summary": result.summary,
            "fields": result.fields,
            "warnings": result.warnings,
            "component_spec": draft.data,
        }

    async def create_catalog_build(
        self,
        *,
        category_code: str,
        part_type_code: str,
        component_name: str,
        standard_number: str | None = None,
        version: str = "1.0.0",
        status: str = "draft",
    ) -> dict:
        category, part = resolve_part(category_code, part_type_code)
        component_id = await self.repository.next_component_id(part.id_prefix)
        return await self.create_build(
            catalog_node_id=part.catalog_node_id,
            component_id=component_id,
            component_name=component_name,
            component_type=part.code,
            component_subtype=None,
            family=category.code,
            standard_number=standard_number,
            version=version,
            default_dn=None,
            default_pn=None,
            status=status,
        )

    async def attach_step(self, build_id: UUID, *, model_id: UUID, revision_id: UUID) -> dict:
        build = await self.repository.attach_step(build_id, model_id=model_id, revision_id=revision_id)
        return self._build_payload(build)

    async def update_catalog_build(
        self,
        build_id: UUID,
        *,
        category_code: str,
        part_type_code: str,
        component_name: str,
        standard_number: str | None = None,
        version: str = "1.0.0",
    ) -> dict:
        category, part = resolve_part(category_code, part_type_code)
        build = await self.repository.update_build(
            build_id,
            catalog_node_id=part.catalog_node_id,
            component_name=component_name,
            component_type=part.code,
            component_subtype=None,
            family=category.code,
            standard_number=standard_number,
            version=version,
        )
        return self._build_payload(build)

    async def attach_drawing(self, build_id: UUID, *, task_id: UUID) -> dict:
        build = await self.repository.attach_drawing(build_id, task_id=task_id)
        return self._build_payload(build)

    async def set_status(
        self,
        build_id: UUID,
        *,
        status: str,
        message: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict:
        await self.repository.set_status(
            build_id,
            status=status,
            message=message,
            error_code=error_code,
            error_message=error_message,
        )
        return await self.get_build(build_id)

    async def get_build(self, build_id: UUID) -> dict:
        build = await self._require_build(build_id)
        step = await self._step_source(build)
        drawing = await self._drawing_source(build)
        return self._projected_build_payload(build, step, drawing)

    async def get_status(self, build_id: UUID) -> dict:
        build = await self._require_build(build_id)
        step = await self._step_source(build)
        drawing = await self._drawing_source(build)
        projected = self._projected_build_payload(build, step, drawing)
        return {
            "build_id": str(build.id),
            "status": projected["status"],
            "status_message": build.status_message,
            "error_code": build.error_code,
            "error_message": build.error_message,
            "sources": {"reference_step": step, "drawing": drawing},
        }

    async def _require_build(self, build_id: UUID) -> ComponentBuild:
        build = await self.repository.get_build(build_id)
        if build is None:
            raise ValueError(f"component build not found: {build_id}")
        return build

    async def _step_source(self, build: ComponentBuild) -> dict:
        if build.cad_revision_id is None:
            return {"id": None, "status": "waiting_for_step"}
        source = await self.source_status_reader.get_step_status(build.cad_revision_id)
        return {"id": str(build.cad_revision_id), **source}

    async def _drawing_source(self, build: ComponentBuild) -> dict:
        if build.drawing_task_id is None:
            return {"id": None, "status": "missing"}
        source = await self.source_status_reader.get_drawing_status(build.drawing_task_id)
        return {"id": str(build.drawing_task_id), **source}

    @staticmethod
    def _project_status(build: ComponentBuild, step_status: str, drawing_status: str) -> str:
        if build.status == "source_failed":
            return "source_failed"
        if step_status == "failed" or drawing_status == "failed":
            return "source_failed"
        if drawing_status == "needs_manual_layout":
            return "review_required"
        if step_status == "completed" and drawing_status == "review_ready":
            return "sources_ready"
        if step_status == "completed" and drawing_status in {"waiting_for_step", "missing"}:
            return "sources_partial"
        if build.status == "uploading" and not (build.cad_revision_id and build.drawing_task_id):
            return build.status
        if build.cad_revision_id or build.drawing_task_id:
            return "parsing_sources"
        return build.status

    def _build_payload(self, build: ComponentBuild) -> dict:
        catalog = self._catalog_for_build(build)
        return {
            "id": str(build.id),
            "catalog_node_id": str(build.catalog_node_id) if build.catalog_node_id else None,
            "catalog_path": self._catalog_path(catalog),
            "component_id": build.component_id,
            "component_name": build.component_name,
            "component_type": build.component_type,
            "component_subtype": build.component_subtype,
            "family": build.family,
            "standard_number": build.standard_number,
            "version": build.version,
            "default_dn": build.default_dn,
            "default_pn": build.default_pn,
            "cad_model_id": str(build.cad_model_id) if build.cad_model_id else None,
            "cad_revision_id": str(build.cad_revision_id) if build.cad_revision_id else None,
            "drawing_task_id": str(build.drawing_task_id) if build.drawing_task_id else None,
            "status": build.status,
            "status_message": build.status_message,
            "error_code": build.error_code,
            "error_message": build.error_message,
            "created_at": build.created_at,
            "updated_at": build.updated_at,
        }

    def _projected_build_payload(self, build: ComponentBuild, step: dict, drawing: dict) -> dict:
        payload = self._build_payload(build)
        payload["status"] = self._project_status(build, step["status"], drawing["status"])
        return payload

    async def _category_node(self, category: CatalogCategory, part_builds: dict[str, list[ComponentBuild]]) -> dict:
        return {
            "id": str(category.catalog_node_id),
            "name": category.label,
            "label": category.label,
            "label_en": category.label_en,
            "node_type": "family",
            "category_code": category.code,
            "part_type_code": None,
            "sort_order": category.sort_order,
            "children": [
                await self._part_node(category, part, part_builds.get(part.code, []))
                for part in category.parts
            ],
        }

    async def _part_node(self, category: CatalogCategory, part: CatalogPart, builds: list[ComponentBuild]) -> dict:
        return {
            "id": str(part.catalog_node_id),
            "catalog_node_id": str(part.catalog_node_id),
            "name": part.label,
            "label": part.label,
            "label_en": part.label_en,
            "node_type": "type",
            "category_code": category.code,
            "part_type_code": part.code,
            "sort_order": part.sort_order,
            "children": await self._component_nodes(builds),
        }

    async def _uncategorized_node(self, builds: list[ComponentBuild]) -> dict:
        return {
            "id": "catalog:uncategorized",
            "name": "未分类",
            "label": "未分类",
            "label_en": "Uncategorized",
            "node_type": "family",
            "category_code": "uncategorized",
            "part_type_code": None,
            "sort_order": len(CATEGORIES) + 1,
            "children": [{
                "id": "catalog:uncategorized:type",
                "name": "未分类",
                "label": "未分类",
                "label_en": "Uncategorized",
                "node_type": "type",
                "category_code": "uncategorized",
                "part_type_code": "uncategorized",
                "sort_order": 1,
                "children": await self._component_nodes(builds),
            }],
        }

    async def _component_nodes(self, builds: list[ComponentBuild]) -> list[dict]:
        grouped: dict[str, list[ComponentBuild]] = {}
        for build in builds:
            grouped.setdefault(build.component_id, []).append(build)
        return [
            {
                "id": f"component:{component_id}",
                "name": component_builds[0].component_name,
                "label": component_builds[0].component_name,
                "node_type": "component",
                "component_id": component_id,
                "component_name": component_builds[0].component_name,
                "children": [await self._tree_node(build) for build in component_builds],
            }
            for component_id, component_builds in sorted(grouped.items())
        ]

    async def _tree_node(self, build: ComponentBuild) -> dict:
        step = await self._step_source(build)
        drawing = await self._drawing_source(build)
        component_spec = await self.repository.get_component_spec(build.id)
        projected = self._projected_build_payload(build, step, drawing)
        return {
            "id": str(build.id),
            "build_id": str(build.id),
            "name": build.version,
            "label": f"{build.component_name} {build.version}",
            "node_type": "build",
            "catalog_node_id": projected["catalog_node_id"],
            "catalog_path": projected["catalog_path"],
            "component_id": build.component_id,
            "component_name": build.component_name,
            "status": projected["status"],
            "status_message": build.status_message,
            "error_code": build.error_code,
            "error_message": build.error_message,
            "children": [
                {
                    "id": f"{build.id}:inputs",
                    "build_id": str(build.id),
                    "name": INPUTS_LABEL,
                    "label": INPUTS_LABEL,
                    "node_type": "folder",
                    "status": "pending",
                    "disabled": False,
                    "children": [
                        self._source_node(build, "reference_step", step),
                        self._source_node(build, "drawing", drawing),
                    ],
                },
                {"name": DATA_FUSION_LABEL, "node_type": "data_fusion", "status": "future", "status_label": FUTURE_STATUS_LABEL, "disabled": True},
                {
                    "id": f"{build.id}:component_spec",
                    "build_id": str(build.id),
                    "name": "ComponentSpec",
                    "label": "ComponentSpec",
                    "node_type": "component_spec",
                    "status": "saved" if component_spec else "draft",
                    "status_label": "已保存" if component_spec else "待填写",
                    "disabled": False,
                },
                {"name": PUBLISH_VALIDATION_LABEL, "node_type": "publish_validation", "status": "future", "status_label": FUTURE_STATUS_LABEL, "disabled": True},
            ],
        }

    @staticmethod
    def _catalog_path(catalog: tuple[CatalogCategory, CatalogPart] | None) -> str:
        if catalog is None:
            return "/未分类"
        category, part = catalog
        return f"/{category.label}/{part.label}"

    @staticmethod
    def _catalog_for_build(build: ComponentBuild) -> tuple[CatalogCategory, CatalogPart] | None:
        return find_part_by_node_id(build.catalog_node_id) or find_part_by_legacy_type(build.component_type)

    @staticmethod
    def _raise_missing_build(build_id: UUID):
        raise ValueError(f"component build not found: {build_id}")

    @staticmethod
    def _source_node(build: ComponentBuild, role: str, source: dict) -> dict:
        labels = {"reference_step": "\u53c2\u8003 STEP", "drawing": "\u4e8c\u7ef4\u56fe\u7eb8"}
        target = None
        if source["id"]:
            target = (
                {"revision_id": str(build.cad_revision_id)}
                if role == "reference_step"
                else {"revision_id": str(build.cad_revision_id), "task_id": str(build.drawing_task_id)}
            )
        return {
            "id": f"{build.id}:{role}",
            "build_id": str(build.id),
            "name": labels[role],
            "label": labels[role],
            "node_type": role,
            "status": source["status"],
            "progress": source.get("progress"),
            "status_message": source.get("status_message"),
            "error_code": source.get("error_code"),
            "error_message": source.get("error_message"),
            "disabled": target is None,
            "target": target,
        }
