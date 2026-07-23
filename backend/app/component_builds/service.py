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
    def __init__(self, repository, *, source_status_reader):
        self.repository = repository
        self.source_status_reader = source_status_reader

    async def get_tree(self) -> list[dict]:
        builds = await self.repository.list_builds()
        return [await self._tree_node(build) for build in builds]

    async def create_build(self, **fields) -> dict:
        build = await self.repository.create_build(**fields)
        return self._build_payload(build)

    async def attach_step(self, build_id: UUID, *, model_id: UUID, revision_id: UUID) -> dict:
        build = await self.repository.attach_step(build_id, model_id=model_id, revision_id=revision_id)
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
            return {"id": None, "status": "waiting_for_step"}
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
        if build.status == "uploading" and not (build.cad_revision_id and build.drawing_task_id):
            return build.status
        if build.cad_revision_id or build.drawing_task_id:
            return "parsing_sources"
        return build.status

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

    def _projected_build_payload(self, build: ComponentBuild, step: dict, drawing: dict) -> dict:
        payload = self._build_payload(build)
        payload["status"] = self._project_status(build, step["status"], drawing["status"])
        return payload

    async def _tree_node(self, build: ComponentBuild) -> dict:
        step = await self._step_source(build)
        drawing = await self._drawing_source(build)
        projected = self._projected_build_payload(build, step, drawing)
        return {
            "id": str(build.id),
            "build_id": str(build.id),
            "name": build.version,
            "label": f"{build.component_name} {build.version}",
            "node_type": "build",
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
                {"name": "ComponentSpec", "node_type": "component_spec", "status": "future", "status_label": FUTURE_STATUS_LABEL, "disabled": True},
                {"name": PUBLISH_VALIDATION_LABEL, "node_type": "publish_validation", "status": "future", "status_label": FUTURE_STATUS_LABEL, "disabled": True},
            ],
        }

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
