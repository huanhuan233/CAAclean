from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.component_builds.repository import MemoryComponentBuildRepository, SqlAlchemyComponentBuildRepository
from app.component_builds.service import ComponentBuildService, SqlAlchemySourceStatusReader
from app.db.models import CadModelRevision, CadSpecTask, ComponentBuild


def find_build_node(nodes: list[dict], build_id: str) -> dict:
    for node in nodes:
        if node.get("node_type") == "build" and node.get("build_id") == build_id:
            return node
        found = find_build_node(node.get("children", []), build_id)
        if found:
            return found
    return {}


class FakeSourceStatusReader:
    async def get_step_status(self, revision_id):
        return {"status": "processing", "progress": 40}

    async def get_drawing_status(self, task_id):
        return {"status": "review_ready"}


def test_component_build_has_source_links():
    columns = ComponentBuild.__table__.columns

    assert columns["cad_model_id"].nullable is True
    assert columns["cad_revision_id"].nullable is True
    assert columns["drawing_task_id"].nullable is True
    assert columns["component_id"].nullable is False


@pytest.mark.asyncio
async def test_status_projects_linked_source_states():
    model_id = uuid4()
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository(revision_models={revision_id: model_id})
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    status = await service.get_status(build.id)

    assert status["status"] == "parsing_sources"
    assert status["sources"]["reference_step"]["status"] == "processing"
    assert status["sources"]["drawing"]["status"] == "missing"


@pytest.mark.asyncio
async def test_status_prioritizes_failed_sources_and_manual_layout_review():
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={task_id: revision_id},
    )
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=task_id)

    class FailedStepStatusReader:
        async def get_step_status(self, revision_id):
            return {"status": "failed"}

        async def get_drawing_status(self, task_id):
            return {"status": "needs_manual_layout"}

    status = await ComponentBuildService(repository, source_status_reader=FailedStepStatusReader()).get_status(build.id)

    assert status["status"] == "source_failed"


@pytest.mark.asyncio
async def test_tree_detail_and_status_share_the_same_projected_build_status():
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={task_id: revision_id},
    )
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        status="parsing_sources",
    )
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=task_id)

    class ReadySourceStatusReader:
        async def get_step_status(self, _revision_id):
            return {"status": "completed", "progress": 100}

        async def get_drawing_status(self, _task_id):
            return {"status": "review_ready", "progress": 100}

    service = ComponentBuildService(repository, source_status_reader=ReadySourceStatusReader())

    tree = await service.get_tree()
    detail = await service.get_build(build.id)
    source_status = await service.get_status(build.id)

    assert find_build_node(tree, str(build.id))["status"] == "sources_ready"
    assert detail["status"] == "sources_ready"
    assert source_status["status"] == "sources_ready"


@pytest.mark.asyncio
async def test_unlinked_build_retains_persisted_upload_failure_status():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        status="source_failed",
    )
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    detail = await service.get_build(build.id)
    status = await service.get_status(build.id)

    assert detail["status"] == "source_failed"
    assert status["status"] == "source_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step_status", "drawing_status"),
    [("completed", "review_ready"), ("processing", "needs_manual_layout")],
)
async def test_persisted_source_failure_overrides_ready_and_manual_source_states(step_status, drawing_status):
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={task_id: revision_id},
    )
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        status="source_failed",
    )
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=task_id)
    class SourceStatusReader:
        async def get_step_status(self, _revision_id):
            return {"status": step_status, "progress": 100}

        async def get_drawing_status(self, _task_id):
            return {"status": drawing_status, "progress": 100}

    service = ComponentBuildService(repository, source_status_reader=SourceStatusReader())

    tree = await service.get_tree()
    detail = await service.get_build(build.id)
    status = await service.get_status(build.id)

    assert find_build_node(tree, str(build.id))["status"] == "source_failed"
    assert detail["status"] == "source_failed"
    assert status["status"] == "source_failed"


@pytest.mark.asyncio
async def test_source_status_reader_projects_source_errors_when_available():
    revision = SimpleNamespace(
        status="failed",
        progress=100,
        status_message="parser failed",
        error_code="freecad_failed",
        error_message="FreeCAD exited",
    )
    task = SimpleNamespace(status="failed", progress=100)

    class Session:
        async def get(self, model, _identifier):
            return revision if model is CadModelRevision else task

    reader = SqlAlchemySourceStatusReader(Session())

    step = await reader.get_step_status(uuid4())
    drawing = await reader.get_drawing_status(uuid4())

    assert step["status_message"] == "parser failed"
    assert step["error_code"] == "freecad_failed"
    assert step["error_message"] == "FreeCAD exited"
    assert drawing["status_message"] is None
    assert drawing["error_code"] is None
    assert drawing["error_message"] is None


@pytest.mark.asyncio
async def test_tree_enables_component_spec_while_future_workflow_nodes_stay_disabled():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")

    tree = await ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader()).get_tree()

    version_node = find_build_node(tree, str(build.id))
    assert version_node["build_id"] == str(build.id)
    assert [child["node_type"] for child in version_node["children"]] == [
        "folder", "data_fusion", "component_spec", "publish_validation"
    ]
    fusion, component_spec, publish = version_node["children"][1:]
    assert fusion["disabled"] is True and fusion["status"] == "future"
    assert component_spec["disabled"] is False and component_spec["status"] == "draft"
    assert publish["disabled"] is True and publish["status"] == "future"
    assert fusion["status_label"] == "后续能力"
    assert component_spec["status_label"] == "待填写"
    assert publish["status_label"] == "后续能力"


@pytest.mark.asyncio
async def test_get_build_projects_identity_links_and_timestamps():
    model_id = uuid4()
    revision_id = uuid4()
    drawing_task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={drawing_task_id: revision_id},
    )
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        default_dn=80,
        default_pn=16,
        error_code="source_unavailable",
        error_message="STEP parser did not respond",
    )
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=drawing_task_id)
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    result = await service.get_build(build.id)

    assert result["component_id"] == "xms06"
    assert result["default_dn"] == 80
    assert result["cad_model_id"] == str(model_id)
    assert result["cad_revision_id"] == str(revision_id)
    assert result["drawing_task_id"] == str(drawing_task_id)
    assert result["error_code"] == "source_unavailable"
    assert result["error_message"] == "STEP parser did not respond"
    assert result["created_at"] is not None
    assert result["updated_at"] is not None


@pytest.mark.asyncio
async def test_memory_repository_accepts_explicit_component_version():
    repository = MemoryComponentBuildRepository()

    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        version="2.1.0",
    )

    assert build.version == "2.1.0"


@pytest.mark.asyncio
async def test_memory_repository_defaults_component_version():
    repository = MemoryComponentBuildRepository()

    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")

    assert build.version == "1.0.0"


@pytest.mark.asyncio
async def test_unconfigured_memory_repository_accepts_trusted_source_ids():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=task_id)

    assert build.cad_model_id == model_id
    assert build.cad_revision_id == revision_id
    assert build.drawing_task_id == task_id


@pytest.mark.asyncio
async def test_memory_repository_clears_drawing_when_step_revision_is_replaced():
    model_id = uuid4()
    revision_a = uuid4()
    revision_b = uuid4()
    drawing_task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_a: model_id, revision_b: model_id},
        drawing_task_revisions={drawing_task_id: revision_a},
    )
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_a)
    await repository.attach_drawing(build.id, task_id=drawing_task_id)

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_b)

    assert build.cad_revision_id == revision_b
    assert build.drawing_task_id is None


@pytest.mark.asyncio
async def test_memory_repository_preserves_drawing_when_step_revision_is_reattached():
    model_id = uuid4()
    revision_id = uuid4()
    drawing_task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={drawing_task_id: revision_id},
    )
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=drawing_task_id)

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)

    assert build.drawing_task_id == drawing_task_id


@pytest.mark.asyncio
async def test_memory_repository_lists_newest_builds_first_with_uuid_tie_breaker():
    repository = MemoryComponentBuildRepository()
    timestamp = datetime(2026, 7, 23, tzinfo=timezone.utc)
    oldest = await repository.create_build(
        id=UUID(int=1),
        component_id="old",
        component_name="Old",
        component_type="flange",
        created_at=timestamp - timedelta(seconds=1),
    )
    tied_lower = await repository.create_build(
        id=UUID(int=2),
        component_id="low",
        component_name="Low",
        component_type="flange",
        created_at=timestamp,
    )
    tied_higher = await repository.create_build(
        id=UUID(int=3),
        component_id="high",
        component_name="High",
        component_type="flange",
        created_at=timestamp,
    )

    builds = await repository.list_builds()

    assert [build.id for build in builds] == [tied_higher.id, tied_lower.id, oldest.id]


@pytest.mark.asyncio
async def test_memory_repository_rejects_step_revision_from_another_model():
    model_id = uuid4()
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository(revision_models={revision_id: uuid4()})
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")

    with pytest.raises(ValueError, match="revision does not belong to model"):
        await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)


@pytest.mark.asyncio
async def test_memory_repository_rejects_drawing_task_from_another_revision():
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={task_id: uuid4()},
    )
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)

    with pytest.raises(ValueError, match="drawing task does not belong to build revision"):
        await repository.attach_drawing(build.id, task_id=task_id)


class SourceLookupSession:
    def __init__(self, build, revision, task):
        self.build = build
        self.revision = revision
        self.task = task

    async def get(self, model, _identifier):
        if model is ComponentBuild:
            return self.build
        if model is CadModelRevision:
            return self.revision
        if model is CadSpecTask:
            return self.task
        return None

    async def commit(self):
        return None

    async def refresh(self, _build):
        return None


@pytest.mark.asyncio
async def test_sqlalchemy_repository_rejects_step_revision_from_another_model():
    build = ComponentBuild(id=uuid4(), component_id="xms06", component_name="XMS06", component_type="flange")
    session = SourceLookupSession(build, SimpleNamespace(model_id=uuid4()), None)
    repository = SqlAlchemyComponentBuildRepository(session)

    with pytest.raises(ValueError, match="revision does not belong to model"):
        await repository.attach_step(build.id, model_id=uuid4(), revision_id=uuid4())


@pytest.mark.asyncio
async def test_sqlalchemy_repository_rejects_drawing_task_from_another_revision():
    revision_id = uuid4()
    build = ComponentBuild(id=uuid4(), component_id="xms06", component_name="XMS06", component_type="flange", cad_revision_id=revision_id)
    session = SourceLookupSession(build, None, SimpleNamespace(revision_id=uuid4()))
    repository = SqlAlchemyComponentBuildRepository(session)

    with pytest.raises(ValueError, match="drawing task does not belong to build revision"):
        await repository.attach_drawing(build.id, task_id=uuid4())


@pytest.mark.asyncio
async def test_sqlalchemy_repository_clears_drawing_when_step_revision_is_replaced():
    model_id = uuid4()
    revision_a = uuid4()
    revision_b = uuid4()
    drawing_task_id = uuid4()
    build = ComponentBuild(
        id=uuid4(),
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        cad_model_id=model_id,
        cad_revision_id=revision_a,
        drawing_task_id=drawing_task_id,
    )
    session = SourceLookupSession(build, SimpleNamespace(model_id=model_id), None)
    repository = SqlAlchemyComponentBuildRepository(session)

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_b)

    assert build.cad_revision_id == revision_b
    assert build.drawing_task_id is None


@pytest.mark.asyncio
async def test_sqlalchemy_repository_preserves_drawing_when_step_revision_is_reattached():
    model_id = uuid4()
    revision_id = uuid4()
    drawing_task_id = uuid4()
    build = ComponentBuild(
        id=uuid4(),
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        cad_model_id=model_id,
        cad_revision_id=revision_id,
        drawing_task_id=drawing_task_id,
    )
    session = SourceLookupSession(build, SimpleNamespace(model_id=model_id), None)
    repository = SqlAlchemyComponentBuildRepository(session)

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)

    assert build.drawing_task_id == drawing_task_id
