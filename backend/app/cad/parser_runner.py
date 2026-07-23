from __future__ import annotations

import asyncio
from functools import partial
import json
import os
import signal
import subprocess
from pathlib import Path
from uuid import UUID

from app.cad.result_validator import validate_parser_result
from app.core.config import Settings


MAX_CAPTURE_CHARS = 12000


class FreeCadParserError(RuntimeError):
    pass


def _truncate(value: bytes) -> str:
    text = value.decode("utf-8", errors="replace")
    if len(text) <= MAX_CAPTURE_CHARS:
        return text
    return text[-MAX_CAPTURE_CHARS:]


async def run_freecad_parser(
    source_file: Path,
    revision_id: UUID,
    work_dir: Path,
    settings: Settings,
) -> dict:
    script_path = Path(settings.cad_script_dir) / "parse_step.py"
    if not script_path.exists():
        raise FreeCadParserError(f"parser script not found: {script_path}")
    if not source_file.exists():
        raise FreeCadParserError(f"source STEP file not found: {source_file}")

    work_dir.mkdir(parents=True, exist_ok=True)
    job_path = work_dir / "job.json"
    result_path = work_dir / "result.json"
    job = {
        "revision_id": str(revision_id),
        "source_file_path": str(source_file),
        "result_json_path": str(result_path),
        "mesh_deflection": settings.cad_mesh_deflection,
    }
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["LIBGL_ALWAYS_SOFTWARE"] = "1"
    if os.name == "nt":
        inherited_path = next((value for key, value in env.items() if key.lower() == "path"), "")
        for key in [key for key in env if key.lower() == "path"]:
            del env[key]
        freecad_bin = Path(settings.freecad_cmd).resolve().parent
        if freecad_bin.name.lower() == "bin" and freecad_bin.parent.name.lower() == "library":
            conda_prefix = freecad_bin.parents[1]
            runtime_paths = [
                conda_prefix,
                conda_prefix / "Library" / "mingw-w64" / "bin",
                conda_prefix / "Library" / "usr" / "bin",
                conda_prefix / "Library" / "bin",
                conda_prefix / "Scripts",
                conda_prefix / "bin",
            ]
        else:
            runtime_paths = [freecad_bin]
        env["PATH"] = os.pathsep.join([*(str(path) for path in runtime_paths), inherited_path])

    process_kwargs: dict[str, object] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": env,
    }
    command = [settings.freecad_cmd, str(script_path), str(job_path)]
    stdin_payload: bytes | None = None
    if os.name == "nt":
        # Windows FreeCADCmd 1.0 treats positional .py files as import targets.
        # Console mode executes Python from stdin reliably when paths are ASCII.
        bootstrap = (
            "import sys; "
            f"sys.argv=[r'{script_path}', r'{job_path}']; "
            f"exec(compile(open(r'{script_path}', encoding='utf-8').read(), r'{script_path}', 'exec'))\n"
        )
        command = [settings.freecad_cmd, "-c"]
        process_kwargs["stdin"] = subprocess.PIPE
        stdin_payload = bootstrap.encode("utf-8")
    else:
        process_kwargs["start_new_session"] = True

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(
            _run_parser_process,
            command,
            process_kwargs,
            stdin_payload,
            settings.freecad_timeout,
            result_path,
        ),
    )


def _run_parser_process(
    command: list[str],
    process_kwargs: dict[str, object],
    stdin_payload: bytes | None,
    timeout: int,
    result_path: Path,
) -> dict:
    process = subprocess.Popen(command, **process_kwargs)
    try:
        stdout, stderr = process.communicate(input=stdin_payload, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate_process(process)
        stdout, stderr = process.communicate()
        raise FreeCadParserError(
            f"FreeCAD parser timed out after {timeout}s; stdout={_truncate(stdout)}; stderr={_truncate(stderr)}"
        ) from exc

    if process.returncode != 0:
        raise FreeCadParserError(
            "FreeCAD parser failed with exit code "
            f"{process.returncode}; stdout={_truncate(stdout)}; stderr={_truncate(stderr)}"
        )
    if not result_path.exists():
        raise FreeCadParserError(f"FreeCAD parser did not produce result.json: {result_path}")

    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        validate_parser_result(data)
        return data
    except json.JSONDecodeError as exc:
        raise FreeCadParserError(f"invalid parser result JSON: {exc}") from exc


def _terminate_process(process) -> None:
    try:
        if os.name != "nt" and process.pid:
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
