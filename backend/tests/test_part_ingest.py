import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.component_builds.ingest import (
    IngestStageError,
    _build_feature_center,
    _run_catpart_route,
    _run_command,
    _run_remote_catpart_worker,
    _decode_process_output,
    IngestSourceError,
    identify_source,
    redact_local_paths,
    safe_asset_path,
    unexpected_error_message,
)
from app.component_builds import ingest as ingest_module
from app.core.config import Settings


@pytest.mark.parametrize(
    ("name", "source_format", "route"),
    [
        ("part.step", "STEP", "step_cad_parse"),
        ("PART.STP", "STEP", "step_cad_parse"),
        ("assembly.CATProduct", "CATPRODUCT", "catia_feature_center"),
        ("assembly.catproduct", "CATPRODUCT", "catia_feature_center"),
        ("assembly_bundle.zip", "CATPRODUCT", "catia_feature_center"),
        ("零件 (终版).CATPart", "CATPART", "catia_feature_center"),
        ("零件.catpart", "CATPART", "catia_feature_center"),
    ],
)
def test_source_format_is_derived_from_real_file_name(name, source_format, route):
    source = identify_source(name)

    assert source.source_format == source_format
    assert source.processing_route == route


@pytest.mark.parametrize("name", ["wrong.cart", "part"])
def test_unsupported_source_is_rejected(name):
    with pytest.raises(IngestSourceError) as error:
        identify_source(name)

    assert error.value.code == "UNSUPPORTED_SOURCE_FORMAT"


def test_asset_path_cannot_escape_task_directory(tmp_path):
    root = tmp_path / "task"
    root.mkdir()
    valid = root / "feature-center" / "lightweight" / "model.glb"
    valid.parent.mkdir(parents=True)
    valid.write_bytes(b"glTF")

    assert safe_asset_path(root, "feature-center/lightweight/model.glb") == valid
    with pytest.raises(IngestSourceError):
        safe_asset_path(root, "../secret.txt")
    with pytest.raises(IngestSourceError):
        safe_asset_path(root, str(Path(tmp_path) / "outside.glb"))


def test_external_tool_error_does_not_expose_local_absolute_path():
    message = redact_local_paths(r"CATIA failed at D:\cad-work\task\source.CATPart")

    assert "D:\\" not in message
    assert "<local_path>" in message


def test_empty_unexpected_error_keeps_exception_type_for_diagnostics():
    assert unexpected_error_message(RuntimeError()) == "未预期异常：RuntimeError"


def test_windows_child_process_gbk_error_keeps_chinese_message():
    message = "Feature Center 输出目录已存在：feature-center"

    assert _decode_process_output(message.encode("gbk")) == message


@pytest.mark.asyncio
async def test_external_command_does_not_use_asyncio_subprocess_on_windows(monkeypatch):
    """用途：防止 Windows SelectorEventLoop 再次因不支持异步子进程而抛出 NotImplementedError。"""
    captured = {}

    class FakeProcess:
        returncode = 0

        def communicate(self, timeout):
            captured["timeout"] = timeout
            return b"ok", b""

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    async def unsupported_async_subprocess(*_args, **_kwargs):
        raise NotImplementedError()

    monkeypatch.setattr(ingest_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(ingest_module.asyncio, "create_subprocess_exec", unsupported_async_subprocess)

    await _run_command(["feature-center.exe", "build"], "FEATURE_CENTER_FAILED", "feature_center_processing", 12)

    assert captured["command"] == ["feature-center.exe", "build"]
    assert captured["timeout"] == 12
    assert captured["kwargs"]["cwd"]


@pytest.mark.asyncio
async def test_same_revision_cannot_be_scheduled_twice(monkeypatch):
    revision_id = uuid4()
    calls = []
    release = asyncio.Event()

    async def fake_pipeline(requested_id, _settings):
        calls.append(requested_id)
        await release.wait()

    monkeypatch.setattr(ingest_module, "run_ingest_pipeline", fake_pipeline)
    ingest_module._INGEST_TASKS.clear()
    settings = Settings(database_url_value="postgresql+asyncpg://postgres@localhost/test")

    ingest_module.schedule_ingest(revision_id, settings)
    ingest_module.schedule_ingest(revision_id, settings)
    await asyncio.sleep(0)

    assert calls == [revision_id]
    release.set()
    await asyncio.gather(*ingest_module._INGEST_TASKS.values())


@pytest.mark.asyncio
async def test_disabled_catpart_worker_fails_before_any_external_parser(tmp_path):
    revision_id = uuid4()
    revision = SimpleNamespace(id=revision_id, source_file_path=str(tmp_path / "part.CATPart"))

    class Repository:
        async def get_revision(self, requested_id):
            assert requested_id == revision_id
            return revision

    settings = Settings(
        database_url_value="postgresql+asyncpg://postgres@localhost/test",
        cad_work_dir=tmp_path,
        catia_worker_mode="disabled",
    )

    with pytest.raises(IngestStageError) as error:
        await _run_catpart_route(Repository(), revision_id, settings)

    assert error.value.code == "catia_worker_disabled"
    assert error.value.stage == "dispatching_caa"


@pytest.mark.asyncio
async def test_feature_center_success_marks_revision_ready(tmp_path, monkeypatch):
    revision_id = uuid4()
    status_updates = []

    class Repository:
        async def update_revision_manifest(self, requested_id, payload):
            assert requested_id == revision_id
            assert payload["viewer_asset"]["glb"] == "feature-center/lightweight/model.glb"
            assert payload["feature_center"]["mapping_available"] is False
            assert payload["feature_center"]["feature_face_mapping_count"] == 0

        async def set_revision_status(self, requested_id, **fields):
            assert requested_id == revision_id
            status_updates.append(fields)

    async def fake_run_command(command, *_args, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        (output / "lightweight").mkdir(parents=True)
        (output / "manifest.json").write_text("{}", encoding="utf-8")
        (output / "lightweight" / "model.glb").write_bytes(b"glTF")
        (output / "lightweight" / "face_mesh_map.json").write_text("{}", encoding="utf-8")
        (output / "lightweight" / "feature_mesh_map.json").write_text("{}", encoding="utf-8")
        (output / "canonical_features.jsonl").write_text("", encoding="utf-8")
        (output / "feature_geometry_links.jsonl").write_text("", encoding="utf-8")
        (output / "measurements.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr("app.component_builds.ingest._run_command", fake_run_command)
    settings = Settings(
        database_url_value="postgresql+asyncpg://postgres@localhost/test",
        cad_work_dir=tmp_path,
    )

    await _build_feature_center(Repository(), revision_id, settings, tmp_path / "part.stp", None)

    assert status_updates[-1] == {
        "status": "completed",
        "progress": 100,
        "status_message": "ready",
        "error_code": None,
        "error_message": None,
    }


@pytest.mark.asyncio
async def test_remote_worker_completion_does_not_mark_viewer_ready_before_sidecar(tmp_path, monkeypatch):
    revision_id = uuid4()
    source = tmp_path / "part.CATPart"
    source.write_bytes(b"CATPart")
    status_updates = []

    class Repository:
        async def set_revision_status(self, requested_id, **fields):
            assert requested_id == revision_id
            status_updates.append(fields)

        async def update_revision_manifest(self, requested_id, payload):
            assert requested_id == revision_id

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def process(self, _source, download_root, report_stage):
            import zipfile
            download_root.mkdir(parents=True)
            with zipfile.ZipFile(download_root / "native_bundle.zip", "w") as archive:
                archive.writestr("features.jsonl", "{}\n")
            (download_root / "exported.stp").write_bytes(b"STEP")
            await report_stage({"stage": "publishing_artifacts", "progress": 65})
            return SimpleNamespace(worker_job_id="worker-1", status="completed", stage="completed")

    monkeypatch.setattr("app.component_builds.ingest.CatiaWorkerClient", Client)
    settings = Settings(
        database_url_value="postgresql+asyncpg://postgres@localhost/test",
        cad_work_dir=tmp_path,
        catia_worker_mode="http",
        catia_worker_url="http://worker.invalid",
    )

    await _run_remote_catpart_worker(Repository(), revision_id, settings, str(source), tmp_path / str(revision_id))

    assert all(update.get("status") != "completed" for update in status_updates)
