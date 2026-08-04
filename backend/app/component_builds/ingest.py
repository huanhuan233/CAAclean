"""统一零件上传的格式识别、后台编排和受控资产定位。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.cad.repository import CadRepository
from app.cad.service import CadService
from app.core.config import REPOSITORY_ROOT, Settings
from app.db.session import SessionLocal


@dataclass(frozen=True)
class IngestSource:
    source_format: str
    processing_route: str
    extension: str


class IngestSourceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class IngestStageError(RuntimeError):
    def __init__(self, code: str, stage: str, message: str):
        super().__init__(message)
        self.code = code
        self.stage = stage


_CATIA_LIMITER = asyncio.Semaphore(1)
_INGEST_TASKS: set[asyncio.Task[None]] = set()
_LOCAL_PATH_PATTERN = re.compile(r"(?i)(?:[a-z]:[\\/]|\\\\)[^\r\n]*")
LOGGER = logging.getLogger(__name__)


class _IngestRuntimeSettings(BaseSettings):
    """用途：只读取零件编排所需外部工具路径，不改变全局 Settings 的用户改动。"""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    caa_rade_root: str = ""
    caa_prereq_root: str = ""


# 用途：只根据已校验文件名识别真实格式，绝不接受客户端指定处理路线。
def identify_source(file_name: str) -> IngestSource:
    extension = Path(Path(file_name).name).suffix.lower()
    if extension in {".step", ".stp"}:
        return IngestSource("STEP", "step_cad_parse", extension)
    if extension == ".catpart":
        return IngestSource("CATPART", "catia_feature_center", extension)
    raise IngestSourceError(
        "UNSUPPORTED_SOURCE_FORMAT",
        "仅支持 STEP、STP 和 CATPart 文件；不支持 .cart",
    )


# 用途：把浏览器请求的相对资产限定在当前任务目录内，阻止目录穿越和绝对路径泄露。
def safe_asset_path(task_root: Path, relative_path: str) -> Path:
    root = task_root.resolve()
    candidate_text = Path(relative_path)
    if candidate_text.is_absolute():
        raise IngestSourceError("VIEWER_ASSET_PATH_INVALID", "Viewer 资产路径必须是相对路径")
    candidate = (root / candidate_text).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise IngestSourceError("VIEWER_ASSET_PATH_INVALID", "Viewer 资产路径越过任务目录") from exc
    return candidate


# 用途：从对外错误消息中移除 Windows 绝对路径，完整堆栈只保留在服务日志边界。
def redact_local_paths(message: str) -> str:
    return _LOCAL_PATH_PATTERN.sub("<local_path>", message)


# 用途：把上传任务交给独立数据库会话执行，HTTP 请求只负责入队和返回任务编号。
def schedule_ingest(revision_id: UUID, settings: Settings) -> None:
    task = asyncio.create_task(run_ingest_pipeline(revision_id, settings))
    _INGEST_TASKS.add(task)
    task.add_done_callback(_INGEST_TASKS.discard)


# 用途：按持久化路由串联现有 STEP 或 CATPart 能力，并把每个真实阶段写回 Revision。
async def run_ingest_pipeline(revision_id: UUID, settings: Settings) -> None:
    async with SessionLocal() as session:
        repository = CadRepository(session)
        revision = await repository.get_revision(revision_id)
        if revision is None:
            return
        ingest = dict((revision.parse_manifest or {}).get("ingest", {}))
        route = ingest.get("processing_route")
        try:
            _prepare_generated_outputs(Path(settings.cad_work_dir) / str(revision_id), route)
            if route == "step_cad_parse":
                await _run_step_route(repository, revision_id, settings)
            elif route == "catia_feature_center":
                async with _CATIA_LIMITER:
                    await _run_catpart_route(repository, revision_id, settings)
            else:
                raise IngestStageError("PROCESSING_ROUTE_INVALID", "queued", "任务缺少合法处理路线")
        except IngestStageError as exc:
            await repository.set_revision_status(
                revision_id,
                status="failed",
                progress=100,
                status_message=exc.stage,
                error_code=exc.code,
                error_message=redact_local_paths(str(exc))[:1000],
            )
        except asyncio.CancelledError:
            await repository.set_revision_status(
                revision_id,
                status="failed",
                progress=100,
                status_message="interrupted",
                error_code="PART_INGEST_INTERRUPTED",
                error_message="处理进程被服务停止，可从原任务重试",
            )
            raise
        except Exception as exc:
            LOGGER.exception("零件后台编排发生未预期错误：revision_id=%s", revision_id)
            await repository.set_revision_status(
                revision_id,
                status="failed",
                progress=100,
                status_message="failed",
                error_code="PART_INGEST_UNEXPECTED",
                error_message=redact_local_paths(str(exc))[:1000],
            )


# 用途：复用现有 FreeCAD 解析后再构建统一 Feature Center 轻量化资产。
async def _run_step_route(repository: CadRepository, revision_id: UUID, settings: Settings) -> None:
    before = await repository.get_revision(revision_id)
    ingest = dict((before.parse_manifest or {}).get("ingest", {})) if before else {}
    service = CadService(repository, settings)
    await service.parse_revision(revision_id)
    revision = await repository.get_revision(revision_id)
    if revision is None or revision.status != "completed":
        raise IngestStageError(
            revision.error_code or "STEP_PARSE_FAILED",
            "parsing",
            revision.error_message or "STEP 解析失败",
        )
    await repository.update_revision_manifest(revision_id, {"ingest": ingest})
    await _set_stage(repository, revision_id, "lightweighting", 80)
    await _build_feature_center(repository, revision_id, settings, Path(revision.source_file_path), None)


# 用途：先运行已有 CAA 原生解析，再用 Automation ExportData 导出 STEP，最后调用既有 Sidecar。
async def _run_catpart_route(repository: CadRepository, revision_id: UUID, settings: Settings) -> None:
    revision = await repository.get_revision(revision_id)
    if revision is None:
        return
    task_root = Path(settings.cad_work_dir) / str(revision_id)
    native_bundle = task_root / "native-caa"
    exported_step = task_root / "exported.stp"
    export_report = task_root / "step-export.json"
    runtime = _IngestRuntimeSettings()
    rade_root = os.environ.get("CAA_RADE_ROOT") or runtime.caa_rade_root
    prereq_root = os.environ.get("CAA_PREREQ_ROOT") or runtime.caa_prereq_root
    if not rade_root or not prereq_root:
        raise IngestStageError("CATIA_WORKER_UNAVAILABLE", "parsing", "未配置 CAA_RADE_ROOT 或 CAA_PREREQ_ROOT")

    await _set_stage(repository, revision_id, "parsing", 15)
    await _run_command(
        [
            "cmd.exe", "/d", "/c", str(REPOSITORY_ROOT / "3DjiexiCAA" / "tools" / "run_r21_x86.bat"),
            "--input", str(revision.source_file_path), "--output", str(native_bundle), "--read-only",
        ],
        "CATIA_WORKER_FAILED",
        "parsing",
        settings.freecad_timeout,
        {"CAA_RADE_ROOT": rade_root, "CAA_PREREQ_ROOT": prereq_root},
    )
    await _set_stage(repository, revision_id, "exporting_step", 45)
    await _run_command(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(REPOSITORY_ROOT / "3DjiexiCAA" / "tools" / "export_catpart_step.ps1"),
            "-InputCatPart", str(revision.source_file_path),
            "-OutputStep", str(exported_step),
            "-ReportPath", str(export_report),
        ],
        "CATIA_EXPORT_FAILED",
        "exporting_step",
        settings.freecad_timeout,
    )
    await _set_stage(repository, revision_id, "feature_center_processing", 70)
    await _build_feature_center(repository, revision_id, settings, exported_step, native_bundle)


# 用途：调用仓库已有 Sidecar CLI 生成并校验 Bundle，不在 Web 层复制任何几何算法。
async def _build_feature_center(
    repository: CadRepository,
    revision_id: UUID,
    settings: Settings,
    step_path: Path,
    native_bundle: Path | None,
) -> None:
    task_root = Path(settings.cad_work_dir) / str(revision_id)
    bundle = task_root / "feature-center"
    command = [
        sys.executable,
        str(REPOSITORY_ROOT / "backend" / "scripts" / "feature_center.py"),
        "build", "--step", str(step_path), "--output", str(bundle),
        "--visual-review-mode", "disabled",
    ]
    if native_bundle is not None:
        command.extend(["--native-bundle", str(native_bundle)])
    await _run_command(command, "FEATURE_CENTER_FAILED", "feature_center_processing", settings.freecad_timeout)
    required = (
        "manifest.json",
        "lightweight/model.glb",
        "lightweight/face_mesh_map.json",
        "lightweight/feature_mesh_map.json",
        "canonical_features.jsonl",
        "feature_geometry_links.jsonl",
        "measurements.jsonl",
    )
    missing = [name for name in required if not (bundle / name).is_file()]
    if missing or (bundle / "lightweight" / "model.glb").stat().st_size == 0:
        raise IngestStageError("VIEWER_ASSET_MISSING", "lightweighting", ",".join(missing) or "model.glb 为空")
    json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    await repository.update_revision_manifest(
        revision_id,
        {
            "viewer_asset": {
                "bundle_root": "feature-center",
                "glb": "feature-center/lightweight/model.glb",
                "scene_manifest": "feature-center/manifest.json",
                "face_mesh_map": "feature-center/lightweight/face_mesh_map.json",
                "feature_mesh_map": "feature-center/lightweight/feature_mesh_map.json",
            },
            "feature_center": {
                "available": (bundle / "canonical_features.jsonl").stat().st_size > 0,
                "bundle_available": True,
                "canonical_features": "feature-center/canonical_features.jsonl",
                "feature_geometry_links": "feature-center/feature_geometry_links.jsonl",
                "measurements": "feature-center/measurements.jsonl",
            },
        },
    )
    await repository.set_revision_status(
        revision_id,
        status="completed",
        progress=100,
        status_message="ready",
        error_code=None,
        error_message=None,
    )


# 用途：重试时只清理本任务生成物，保留上传源文件和持久化任务记录。
def _prepare_generated_outputs(task_root: Path, route: str | None) -> None:
    generated = [task_root / "feature-center"]
    if route == "catia_feature_center":
        generated.extend([
            task_root / "native-caa",
            task_root / "exported.stp",
            task_root / "step-export.json",
        ])
    for path in generated:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()


# 用途：更新处理中间阶段，同时保留上传时写入的格式、路线和源文件追溯信息。
async def _set_stage(repository: CadRepository, revision_id: UUID, stage: str, progress: int) -> None:
    await repository.set_revision_status(
        revision_id,
        status="processing",
        progress=progress,
        status_message=stage,
        error_code=None,
        error_message=None,
    )


# 用途：异步执行现有外部工具，统一处理超时、退出码和可读诊断。
async def _run_command(
    command: list[str],
    error_code: str,
    stage: str,
    timeout_seconds: int,
    environment: dict[str, str] | None = None,
) -> None:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(REPOSITORY_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **(environment or {})},
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=max(1, timeout_seconds))
    except asyncio.TimeoutError as exc:
        if "process" in locals():
            await _terminate_process_tree(process)
        raise IngestStageError(error_code, stage, "处理超时") from exc
    except asyncio.CancelledError:
        if "process" in locals():
            await asyncio.shield(_terminate_process_tree(process))
        raise
    if process.returncode != 0:
        detail = (stderr or stdout).decode("utf-8", errors="replace").strip()
        LOGGER.error("外部处理命令失败：stage=%s command=%s detail=%s", stage, command[0], detail)
        raise IngestStageError(error_code, stage, redact_local_paths(detail[-1000:]) or f"退出码 {process.returncode}")


# 用途：终止本任务启动的完整外部进程树，防止超时或服务停止后残留 CATIA 子进程。
async def _terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec(
            "taskkill.exe",
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.communicate()
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    await process.wait()
