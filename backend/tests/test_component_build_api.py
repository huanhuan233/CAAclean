from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.cad.router import get_cad_service
from app.component_builds.repository import MemoryComponentBuildRepository
from app.component_builds.router import get_component_build_service
from app.component_builds.service import ComponentBuildService
from app.core.config import Settings, get_settings
from app.drawing.router import get_drawing_service
from app.main import app


PNG_BYTES = b"\x89PNG\r\n\x1a\n"


def find_node(nodes: list[dict], node_type: str) -> dict:
    for node in nodes:
        if node["node_type"] == node_type:
            return node
        found = find_node(node.get("children", []), node_type)
        if found:
            return found
    return {}


class FakeSourceStatusReader:
    async def get_step_status(self, _revision_id):
        return {"status": "queued", "progress": 0}

    async def get_drawing_status(self, _task_id):
        return {"status": "created", "progress": 0}


class FakeCadService:
    def __init__(self):
        self.model_id = uuid4()
        self.revision_id = uuid4()
        self.uploads = []

    async def create_model_from_upload(self, file, name):
        self.uploads.append((file.filename, name))
        return {"model_id": self.model_id, "revision_id": self.revision_id, "status": "queued"}


class FakeDrawingService:
    def __init__(self):
        self.task_id = uuid4()
        self.created = []

    async def create_task(self, *, revision_id, drawing_file, target_code, target_dn):
        self.created.append((revision_id, drawing_file, target_code, target_dn))
        return SimpleNamespace(id=self.task_id)


@pytest.fixture
def component_client(tmp_path, monkeypatch):
    repository = MemoryComponentBuildRepository()
    build_service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())
    cad_service = FakeCadService()
    drawing_service = FakeDrawingService()
    settings = Settings(cad_spec_work_dir=tmp_path)
    scheduled = []

    def schedule(task_id, _settings, *, target_code, target_dn):
        scheduled.append((task_id, target_code, target_dn))

    monkeypatch.setattr("app.component_builds.router.schedule_drawing_pipeline", schedule)
    app.dependency_overrides[get_component_build_service] = lambda: build_service
    app.dependency_overrides[get_cad_service] = lambda: cad_service
    app.dependency_overrides[get_drawing_service] = lambda: drawing_service
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield TestClient(app), cad_service, drawing_service, scheduled
    finally:
        app.dependency_overrides.clear()


def create_build(client: TestClient):
    return client.post(
        "/api/component-builds",
        data={
            "component_id": "xms06",
            "component_name": "XMS06",
            "component_type": "flange",
            "version": "1.0.0",
            "default_dn": "80",
            "default_pn": "16",
        },
        files={
            "step_file": ("XMS06-DN80.stp", b"ISO-10303-21;", "application/octet-stream"),
            "drawing_file": ("XMS06.png", PNG_BYTES, "image/png"),
        },
    )


def test_create_build_links_step_and_drawing(component_client):
    client, cad_service, drawing_service, scheduled = component_client

    response = create_build(client)

    assert response.status_code == 202
    assert response.json()["cad_revision_id"] == str(cad_service.revision_id)
    assert response.json()["drawing_task_id"] == str(drawing_service.task_id)
    assert drawing_service.created[0][0] == cad_service.revision_id
    assert drawing_service.created[0][1].exists()
    assert scheduled == [(drawing_service.task_id, "xms06", 80)]


def test_tree_exposes_specialist_targets(component_client):
    client, cad_service, drawing_service, _ = component_client
    create_build(client)

    response = client.get("/api/component-builds/tree")

    assert response.status_code == 200
    step = find_node(response.json(), "reference_step")
    drawing = find_node(response.json(), "drawing")
    assert step["target"]["revision_id"] == str(cad_service.revision_id)
    assert drawing["target"]["task_id"] == str(drawing_service.task_id)


def test_step_retry_requires_reupload(component_client):
    client, _, _, _ = component_client
    build = create_build(client).json()

    response = client.post(f"/api/component-builds/{build['id']}/retry", json={"role": "reference_step"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "step_reupload_required"


def test_query_and_drawing_retry_return_projected_build(component_client):
    client, _, drawing_service, scheduled = component_client
    build = create_build(client).json()

    detail = client.get(f"/api/component-builds/{build['id']}")
    status = client.get(f"/api/component-builds/{build['id']}/status")
    retry = client.post(f"/api/component-builds/{build['id']}/retry", json={"role": "drawing"})

    assert detail.status_code == 200
    assert detail.json()["drawing_task_id"] == str(drawing_service.task_id)
    assert status.status_code == 200
    assert status.json()["sources"]["drawing"]["status"] == "created"
    assert retry.status_code == 202
    assert retry.json()["status"] == "parsing_sources"
    assert scheduled[-1] == (drawing_service.task_id, "xms06", 80)
