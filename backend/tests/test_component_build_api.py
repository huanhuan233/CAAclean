from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.cad.router import get_cad_service
from app.component_builds.repository import MemoryComponentBuildRepository
from app.component_builds.router import get_component_build_service, run_drawing_pipeline
from app.component_builds.service import ComponentBuildService
from app.core.config import Settings, get_settings
from app.drawing.schemas import DrawingError
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
        yield TestClient(app), cad_service, drawing_service, scheduled, build_service
    finally:
        app.dependency_overrides.clear()


def create_build(client: TestClient, *, step_name: str = "XMS06-DN80.stp", drawing_name: str = "XMS06.png"):
    return client.post(
        "/api/component-builds",
        data={
            "category_code": "connection-fastening",
            "part_type_code": "flange",
            "component_name": "XMS06",
            # This legacy value must not influence the generated component ID.
            "component_id": "user-supplied-id",
        },
        files={
            "step_file": (step_name, b"ISO-10303-21;", "application/octet-stream"),
            "drawing_file": (drawing_name, PNG_BYTES, "image/png"),
        },
    )


def test_create_build_links_step_and_drawing(component_client):
    client, cad_service, drawing_service, scheduled, _ = component_client

    response = create_build(client)

    assert response.status_code == 202
    assert response.json()["component_id"] == "flange-001"
    assert response.json()["catalog_path"] == "/连接与紧固类/法兰"
    assert response.json()["default_dn"] is None
    assert response.json()["default_pn"] is None
    assert response.json()["cad_revision_id"] == str(cad_service.revision_id)
    assert response.json()["drawing_task_id"] == str(drawing_service.task_id)
    assert drawing_service.created[0][0] == cad_service.revision_id
    assert drawing_service.created[0][1].exists()
    assert drawing_service.created[0][2:] == ("flange-001", None)
    assert scheduled == [(drawing_service.task_id, "flange-001", None)]


def test_catalog_endpoint_returns_categories_and_cascading_parts(component_client):
    client, _, _, _, _ = component_client

    response = client.get("/api/component-builds/catalog")

    assert response.status_code == 200
    categories = response.json()["categories"]
    assert [category["category_code"] for category in categories] == [
        "support-frame", "shaft-transmission", "roller", "connection-fastening", "drive-actuation", "functional"
    ]
    assert any(part["part_type_code"] == "flange" for part in categories[3]["parts"])


def test_rejects_category_part_mismatch_before_a_build_is_created(component_client):
    client, _, _, _, build_service = component_client

    response = client.post(
        "/api/component-builds",
        data={"category_code": "roller", "part_type_code": "flange", "component_name": "错误分类"},
        files={
            "step_file": ("bad.stp", b"ISO-10303-21;", "application/octet-stream"),
            "drawing_file": ("bad.png", PNG_BYTES, "image/png"),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_catalog_selection"
    assert build_service.repository.builds == {}


def test_tree_exposes_specialist_targets(component_client):
    client, cad_service, drawing_service, _, _ = component_client
    create_build(client)

    response = client.get("/api/component-builds/tree")

    assert response.status_code == 200
    step = find_node(response.json(), "reference_step")
    drawing = find_node(response.json(), "drawing")
    assert step["target"]["revision_id"] == str(cad_service.revision_id)
    assert drawing["target"]["revision_id"] == str(cad_service.revision_id)
    assert drawing["target"]["task_id"] == str(drawing_service.task_id)


def test_step_retry_requires_reupload(component_client):
    client, _, _, _, _ = component_client
    build = create_build(client).json()

    response = client.post(f"/api/component-builds/{build['id']}/retry", json={"role": "reference_step"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "step_reupload_required"


def test_query_and_drawing_retry_return_projected_build(component_client):
    client, _, drawing_service, scheduled, _ = component_client
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
    assert scheduled[-1] == (drawing_service.task_id, "flange-001", None)


def test_invalid_extension_is_rejected_before_a_build_is_created(component_client):
    client, _, _, _, build_service = component_client

    response = create_build(client, step_name="XMS06.txt")

    assert response.status_code == 400
    assert build_service.repository.builds == {}


def test_step_upload_failure_marks_build_failed_without_creating_drawing(component_client):
    client, cad_service, drawing_service, _, build_service = component_client

    async def fail_step_upload(_file, _name):
        raise ValueError("invalid STEP payload")

    cad_service.create_model_from_upload = fail_step_upload

    response = create_build(client)

    build = next(iter(build_service.repository.builds.values()))
    assert response.status_code == 400
    assert build.status == "source_failed"
    assert build.error_code == "component_build_upload_failed"
    assert build.error_message == "invalid STEP payload"
    assert build.cad_revision_id is None
    assert drawing_service.created == []


def test_failure_persistence_error_does_not_mask_step_upload_error(component_client):
    client, cad_service, _, _, build_service = component_client

    async def fail_step_upload(_file, _name):
        raise ValueError("invalid STEP payload")

    async def fail_failure_persistence(*_args, **_kwargs):
        raise RuntimeError("database is unavailable")

    cad_service.create_model_from_upload = fail_step_upload
    build_service.set_status = fail_failure_persistence

    response = create_build(client)

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "component_build_upload_failed",
        "message": "invalid STEP payload",
    }


def test_drawing_creation_failure_keeps_step_and_marks_build_failed(component_client):
    client, cad_service, drawing_service, _, build_service = component_client

    async def fail_drawing_create(**_kwargs):
        raise DrawingError("drawing_decode_failed", "drawing is invalid")

    drawing_service.create_task = fail_drawing_create

    response = create_build(client)

    build = next(iter(build_service.repository.builds.values()))
    assert response.status_code == 400
    assert build.status == "source_failed"
    assert build.error_code == "drawing_decode_failed"
    assert build.error_message == "drawing is invalid"
    assert build.cad_revision_id == cad_service.revision_id
    assert build.drawing_task_id is None


def test_missing_build_returns_not_found(component_client):
    client, _, _, _, _ = component_client

    response = client.get("/api/component-builds/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False


@pytest.mark.asyncio
async def test_drawing_pipeline_persists_unexpected_layout_failure(monkeypatch, tmp_path):
    task_id = uuid4()
    layout_updates = []

    class Drawing:
        repository = SimpleNamespace(
            update_task_status=lambda *args: layout_updates.append(args),
        )
        extraction_repository = SimpleNamespace()

        async def start_layout(self, _task_id):
            raise RuntimeError("layout crashed")

    drawing = Drawing()

    async def update_task_status(*args):
        layout_updates.append(args)

    drawing.repository.update_task_status = update_task_status
    monkeypatch.setattr("app.component_builds.router.SessionLocal", lambda: FakeSessionContext())
    monkeypatch.setattr("app.component_builds.router.create_drawing_service", lambda _session, _settings: drawing)

    await run_drawing_pipeline(task_id, Settings(cad_spec_work_dir=tmp_path), target_code="xms06", target_dn=80)

    assert layout_updates == [(task_id, "failed", "layout_failed", "layout crashed")]


@pytest.mark.asyncio
async def test_drawing_pipeline_persists_unexpected_extraction_failure_separately(monkeypatch, tmp_path):
    task_id = uuid4()
    layout_updates = []
    extraction_updates = []

    class Drawing:
        repository = SimpleNamespace()
        extraction_repository = SimpleNamespace()

        async def start_layout(self, _task_id):
            return {"status": "layout_ready"}

        async def extract_drawing_facts(self, _task_id, *, target_code, target_dn):
            raise RuntimeError("extraction crashed")

    drawing = Drawing()

    async def update_task_status(*args):
        layout_updates.append(args)

    async def set_status(*args):
        extraction_updates.append(args)

    drawing.repository.update_task_status = update_task_status
    drawing.extraction_repository.set_status = set_status
    monkeypatch.setattr("app.component_builds.router.SessionLocal", lambda: FakeSessionContext())
    monkeypatch.setattr("app.component_builds.router.create_drawing_service", lambda _session, _settings: drawing)

    await run_drawing_pipeline(task_id, Settings(cad_spec_work_dir=tmp_path), target_code="xms06", target_dn=80)

    assert layout_updates == []
    assert extraction_updates == [(task_id, "failed", 100, "failed", "drawing_extraction_failed", "extraction crashed")]
