from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.component_builds.repository import MemoryComponentBuildRepository, SqlAlchemyComponentBuildRepository
from app.component_builds.service import ComponentBuildService
from app.db.models import CadModelRevision, CadSpecTask, ComponentBuild


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
    assert status["sources"]["drawing"]["status"] == "waiting_for_step"


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
async def test_tree_adds_future_workflow_nodes_as_disabled():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")

    tree = await ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader()).get_tree()

    version_node = tree[0]
    assert version_node["build_id"] == str(build.id)
    assert [child["name"] for child in version_node["children"]] == [
        "输入资料",
        "数据融合",
        "ComponentSpec",
        "发布校验",
    ]
    assert all(child["disabled"] is True and child["status"] == "future" for child in version_node["children"][1:])
    assert all(child["status_label"] == "后续能力" for child in version_node["children"][1:])


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
