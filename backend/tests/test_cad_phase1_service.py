import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.cad.service import CadService, recover_interrupted_revisions
from app.core.config import Settings


class FakeUpload:
    filename = "part.stp"

    async def read(self):
        return b"ISO-10303-21;"


class FakeCatPartUpload:
    filename = "框架 (终版).CATPart"

    async def read(self):
        return b"CATIA V5 binary fixture"


class FakeRepository:
    def __init__(self, session=None):
        self.session = session
        self.model = SimpleNamespace(id=uuid4())
        self.revision = SimpleNamespace(
            id=uuid4(),
            status="queued",
            source_file_path="pending",
        )
        self.statuses = []
        self.created_fields = None
        self.manifests = []

    async def create_upload_revision(self, **kwargs):
        self.created_fields = kwargs
        return self.model, self.revision

    async def update_revision_manifest(self, revision_id, values):
        self.manifests.append(values)

    async def get_revision(self, revision_id):
        return self.revision

    async def set_revision_status(self, revision_id, **kwargs):
        self.statuses.append(kwargs)

    async def persist_parser_result(self, revision_id, result):
        self.persisted = result


@pytest.mark.asyncio
async def test_upload_schedules_background_parse_with_independent_session(tmp_path, monkeypatch):
    request_repo = FakeRepository(session="request-session")
    background_sessions = []
    background_repos = []
    scheduled = {}

    class FakeSession:
        async def __aenter__(self):
            background_sessions.append(self)
            return self

        async def __aexit__(self, exc_type, exc, tb):
            self.closed = True

    def session_factory():
        return FakeSession()

    def repository_factory(session):
        repo = FakeRepository(session=session)
        repo.revision = request_repo.revision
        background_repos.append(repo)
        return repo

    def fake_create_task(coro):
        scheduled["coro"] = coro
        return SimpleNamespace(cancel=lambda: None)

    async def fake_run_freecad_parser(*args, **kwargs):
        return {
            "revision_id": str(request_repo.revision.id),
            "parser_name": "FreeCAD",
            "parser_version": "1.1.0",
            "schema_version": "cad_parse_v2",
            "summary": {},
            "entities": [],
            "relations": [],
            "meshes": [],
            "parse_manifest": {},
        }

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    monkeypatch.setattr("app.cad.service.run_freecad_parser", fake_run_freecad_parser)

    service = CadService(
        request_repo,
        Settings(cad_work_dir=tmp_path, cad_script_dir=tmp_path),
        session_factory=session_factory,
        repository_factory=repository_factory,
    )

    response = await service.create_model_from_upload(FakeUpload(), None)
    await scheduled["coro"]

    assert response["status"] == "queued"
    assert background_repos[0].statuses[0]["status"] == "processing"
    assert getattr(background_repos[0], "persisted").schema_version == "cad_parse_v2"
    assert background_repos[0].session is background_sessions[0]
    assert background_repos[0].session != "request-session"
    assert background_sessions[0].closed is True


@pytest.mark.asyncio
async def test_generic_source_upload_preserves_unicode_name_and_does_not_auto_parse(tmp_path, monkeypatch):
    repository = FakeRepository(session="request-session")
    created_tasks = []
    monkeypatch.setattr(asyncio, "create_task", lambda coroutine: created_tasks.append(coroutine))
    service = CadService(repository, Settings(cad_work_dir=tmp_path))

    response = await service.create_source_from_upload(
        FakeCatPartUpload(),
        "航空框架",
        source_format="CATPART",
        processing_route="catia_feature_center",
    )

    assert response["source_format"] == "CATPART"
    assert response["processing_route"] == "catia_feature_center"
    assert repository.created_fields["source_file_name"] == "框架 (终版).CATPart"
    assert Path(repository.revision.source_file_path).read_bytes() == b"CATIA V5 binary fixture"
    assert repository.manifests[0]["ingest"]["source_format"] == "CATPART"
    assert created_tasks == []


@pytest.mark.asyncio
async def test_parse_revision_uses_cad_max_concurrency(tmp_path, monkeypatch):
    active = 0
    max_active = 0

    async def fake_run_freecad_parser(*args, **kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        revision_id = args[1]
        return {
            "revision_id": str(revision_id),
            "parser_name": "FreeCAD",
            "parser_version": "1.1.0",
            "schema_version": "cad_parse_v2",
            "summary": {},
            "entities": [],
            "relations": [],
            "meshes": [],
            "parse_manifest": {},
        }

    monkeypatch.setattr("app.cad.service.run_freecad_parser", fake_run_freecad_parser)
    repo = FakeRepository()
    repo.revision.source_file_path = str(tmp_path / "source.stp")
    Path(repo.revision.source_file_path).write_text("ISO-10303-21;", encoding="utf-8")
    service = CadService(repo, Settings(cad_work_dir=tmp_path, cad_max_concurrency=1))

    await asyncio.gather(service.parse_revision(uuid4()), service.parse_revision(uuid4()))

    assert max_active == 1


@pytest.mark.asyncio
async def test_startup_marks_stale_queued_and_processing_revisions_failed():
    calls = []

    class Repo:
        async def fail_interrupted_revisions(self, minutes, error_code):
            calls.append((minutes, error_code))
            return 2

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            self.closed = True

    await recover_interrupted_revisions(
        Settings(cad_stale_job_minutes=7),
        session_factory=lambda: Session(),
        repository_factory=lambda session: Repo(),
    )

    assert calls == [(7, "interrupted_by_service_restart")]
