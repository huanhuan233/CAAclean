from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
        return {"status": revision.status, "progress": revision.progress} if revision else {"status": "missing"}

    async def get_drawing_status(self, task_id: UUID) -> dict:
        task = await self.session.get(CadSpecTask, task_id)
        return {"status": task.status, "progress": task.progress} if task else {"status": "missing"}


class ComponentBuildService:
    def __init__(self, repository, *, source_status_reader):
        self.repository = repository
        self.source_status_reader = source_status_reader

    async def get_tree(self) -> list[dict]:
        builds = await self.repository.list_builds()
        return [self._tree_node(build) for build in builds]

    async def get_build(self, build_id: UUID) -> dict:
        build = await self._require_build(build_id)
        return self._build_payload(build)

    async def get_status(self, build_id: UUID) -> dict:
        build = await self._require_build(build_id)
        step = await self._step_source(build)
        drawing = await self._drawing_source(build)
        return {
            "build_id": str(build.id),
            "status": self._project_status(build, step["status"], drawing["status"]),
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
            return {"id": None, "status": "waiting_for_step"}
        source = await self.source_status_reader.get_drawing_status(build.drawing_task_id)
        return {"id": str(build.drawing_task_id), **source}

    @staticmethod
    def _project_status(build: ComponentBuild, step_status: str, drawing_status: str) -> str:
        if step_status == "failed" or drawing_status == "failed":
            return "source_failed"
        if drawing_status == "needs_manual_layout":
            return "review_required"
        if step_status == "completed" and drawing_status == "review_ready":
            return "sources_ready"
        if build.cad_revision_id or build.drawing_task_id:
            return "parsing_sources"
        return "draft"

    @staticmethod
    def _build_payload(build: ComponentBuild) -> dict:
        return {
            "id": str(build.id),
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

    def _tree_node(self, build: ComponentBuild) -> dict:
        return {
            "id": str(build.id),
            "build_id": str(build.id),
            "name": build.version,
            "node_type": "component_build",
            "component_id": build.component_id,
            "component_name": build.component_name,
            "status": build.status,
            "children": [
                {"name": INPUTS_LABEL, "node_type": "inputs", "status": "pending", "disabled": False},
                {"name": DATA_FUSION_LABEL, "node_type": "data_fusion", "status": "future", "status_label": FUTURE_STATUS_LABEL, "disabled": True},
                {"name": "ComponentSpec", "node_type": "component_spec", "status": "future", "status_label": FUTURE_STATUS_LABEL, "disabled": True},
                {"name": PUBLISH_VALIDATION_LABEL, "node_type": "publish_validation", "status": "future", "status_label": FUTURE_STATUS_LABEL, "disabled": True},
            ],
        }
