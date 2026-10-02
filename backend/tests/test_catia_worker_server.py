import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.catia_worker.server import CatiaWorkerServerSettings, WorkerExecutionError, WorkerService, create_app
from app.catia_worker.caa_new_runner import CaaNewRunner


def test_worker_resolves_relative_work_dir_before_external_process_changes_cwd(tmp_path, monkeypatch):
    """相对任务目录必须先固定为绝对路径，避免 CAA 子进程从仓库根目录解析到错误位置。"""
    monkeypatch.chdir(tmp_path)
    service = WorkerService(CatiaWorkerServerSettings(work_dir=Path("relative-worker")))

    assert service.settings.work_dir == (tmp_path / "relative-worker").resolve()


def test_worker_health_reports_readiness_without_sensitive_paths(tmp_path):
    app = create_app(
        CatiaWorkerServerSettings(
            work_dir=tmp_path,
            token="secret",
            caa_rade_root="D:/fake/rade",
            caa_prereq_root="D:/fake/catia",
        )
    )

    with TestClient(app) as client:
        unauthorized = client.get("/health")
        response = client.get("/health", headers={"Authorization": "Bearer secret"})

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert "D:/fake" not in response.text
    assert response.json()["max_concurrency"] == 1
    assert response.json()["capture_engine"] == "caa_new"
    assert response.json()["capture_platform"] == "intel_a"
    assert response.json()["capture_bitness"] == 32


def test_worker_rejects_non_catia_and_empty_upload(tmp_path):
    app = create_app(CatiaWorkerServerSettings(work_dir=tmp_path))

    with TestClient(app) as client:
        wrong = client.post("/v1/jobs", files={"source_file": ("part.step", b"STEP")})
        empty = client.post("/v1/jobs", files={"source_file": ("part.CATPart", b"")})

    assert wrong.status_code == 415
    assert wrong.json()["detail"]["code"] == "unsupported_format"
    assert empty.status_code == 400
    assert empty.json()["detail"]["code"] == "empty_source_file"


def test_worker_accepts_catproduct_and_preserves_extension_for_caa(tmp_path):
    async def noop_processor(*_args, **_kwargs):
        return None

    app = create_app(CatiaWorkerServerSettings(work_dir=tmp_path), noop_processor)

    with TestClient(app) as client:
        response = client.post("/v1/jobs", files={"source_file": ("assy.CATProduct", b"CATProduct")})

    assert response.status_code == 202
    job_id = response.json()["worker_job_id"]
    assert (tmp_path / job_id / "source.CATProduct").read_bytes() == b"CATProduct"


def test_worker_accepts_catproduct_zip_and_resolves_bundle_entry(tmp_path):
    from app.catia_worker.server import _resolve_job_source

    job_root = tmp_path / "job"
    job_root.mkdir()
    with zipfile.ZipFile(job_root / "source.zip", "w") as archive:
        archive.writestr("assembly/top.CATProduct", b"CATProduct")
        archive.writestr("assembly/parts/part1.CATPart", b"CATPart")

    source = _resolve_job_source(job_root)

    assert source == job_root / "source-bundle" / "top.CATProduct"
    assert (job_root / "source-bundle" / "parts" / "part1.CATPart").read_bytes() == b"CATPart"


def test_worker_prefers_unreferenced_root_catproduct_in_zip(tmp_path):
    from app.catia_worker.server import _resolve_job_source

    job_root = tmp_path / "job"
    job_root.mkdir()
    with zipfile.ZipFile(job_root / "source.zip", "w") as archive:
        archive.writestr("bundle/A_Child.CATProduct", b"child product")
        archive.writestr("bundle/RootAssembly.CATProduct", b"Root references A_Child.CATProduct")

    source = _resolve_job_source(job_root)

    assert source == job_root / "source-bundle" / "RootAssembly.CATProduct"


def test_worker_strips_unicode_common_root_and_keeps_smallest_root_product(tmp_path):
    from app.catia_worker.server import _resolve_job_source

    job_root = tmp_path / "job"
    job_root.mkdir()
    with zipfile.ZipFile(job_root / "source.zip", "w") as archive:
        archive.writestr("连接关系示例数据/510.000 A.CATProduct", b"child product")
        archive.writestr(
            "连接关系示例数据/500.000 A.CATProduct",
            b"root references 510.000 A.CATProduct",
        )
        archive.writestr("连接关系示例数据/510.001 A.CATPart", b"part")

    source = _resolve_job_source(job_root)

    assert source == job_root / "source-bundle" / "500.000 A.CATProduct"
    assert source.parent.as_posix().isascii()
    assert (source.parent / "510.001 A.CATPart").read_bytes() == b"part"


def test_worker_rejects_zip_traversal_after_common_root_stripping(tmp_path):
    from app.catia_worker.server import _resolve_job_source

    job_root = tmp_path / "job"
    job_root.mkdir()
    with zipfile.ZipFile(job_root / "source.zip", "w") as archive:
        archive.writestr("bundle/top.CATProduct", b"CATProduct")
        archive.writestr("bundle/../../outside.CATPart", b"CATPart")

    with pytest.raises(WorkerExecutionError) as error:
        _resolve_job_source(job_root)

    assert error.value.code == "catia_source_bundle_invalid"


def test_worker_rejects_parent_traversal_as_the_only_zip_root(tmp_path):
    from app.catia_worker.server import _resolve_job_source

    job_root = tmp_path / "job"
    job_root.mkdir()
    with zipfile.ZipFile(job_root / "source.zip", "w") as archive:
        archive.writestr("../outside.CATProduct", b"CATProduct")

    with pytest.raises(WorkerExecutionError) as error:
        _resolve_job_source(job_root)

    assert error.value.code == "catia_source_bundle_invalid"


def test_worker_job_id_does_not_reuse_source_file_name(tmp_path):
    app = create_app(CatiaWorkerServerSettings(work_dir=tmp_path, enabled=False))

    with TestClient(app) as client:
        response = client.post("/v1/jobs", files={"source_file": ("零件 (1).CATPart", b"CATPart")})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "catia_worker_disabled"


def test_caa_new_runner_inspects_normalized_manifest(tmp_path):
    native_dir = tmp_path / "native-caa"
    native_dir.mkdir()
    (native_dir / "manifest.json").write_text(
        '{"schema_version":"caa_capture_v1","parser_version":"0.2.0","capture_status":"partial",'
        '"geometry_count":0,"selected_reconstruction_route":"tree_properties"}',
        encoding="utf-8",
    )
    (native_dir / "object_entities.jsonl").write_text("{}\n", encoding="utf-8")
    (native_dir / "tree_occurrences.jsonl").write_text("{}\n", encoding="utf-8")
    (native_dir / "property_facts.jsonl").write_text("{}\n", encoding="utf-8")
    (native_dir / ".cadcapture_stage_owner").write_text("stale-marker", encoding="utf-8")

    result = CaaNewRunner(project_root=tmp_path, runner=tmp_path / "run_r21_x86.bat").inspect(native_dir)

    assert result.schema_version == "caa_capture_v1"
    assert result.parser_version == "0.2.0"
    assert result.capture_status == "partial"
    assert result.has_geometry is False
    assert ".cadcapture_stage_owner" not in result.artifact_paths
