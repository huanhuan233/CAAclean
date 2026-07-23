from uuid import uuid4

import pytest

from app.component_builds.repository import MemoryComponentBuildRepository
from app.component_builds.service import ComponentBuildService
from app.db.models import ComponentBuild


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
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=uuid4(), revision_id=uuid4())
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    status = await service.get_status(build.id)

    assert status["status"] == "parsing_sources"
    assert status["sources"]["reference_step"]["status"] == "processing"
    assert status["sources"]["drawing"]["status"] == "waiting_for_step"


@pytest.mark.asyncio
async def test_status_prioritizes_failed_sources_and_manual_layout_review():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=uuid4(), revision_id=uuid4())
    await repository.attach_drawing(build.id, task_id=uuid4())

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
        "杈撳叆璧勬枡",
        "鏁版嵁铻嶅悎",
        "ComponentSpec",
        "鍙戝竷鏍￠獙",
    ]
    assert all(child["disabled"] is True and child["status"] == "future" for child in version_node["children"][1:])


@pytest.mark.asyncio
async def test_get_build_projects_identity_links_and_timestamps():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        default_dn=80,
        default_pn=16,
    )
    model_id = uuid4()
    revision_id = uuid4()
    drawing_task_id = uuid4()
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=drawing_task_id)
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    result = await service.get_build(build.id)

    assert result["component_id"] == "xms06"
    assert result["default_dn"] == 80
    assert result["cad_model_id"] == str(model_id)
    assert result["cad_revision_id"] == str(revision_id)
    assert result["drawing_task_id"] == str(drawing_task_id)
    assert result["created_at"] is not None
    assert result["updated_at"] is not None
