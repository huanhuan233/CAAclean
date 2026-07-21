from __future__ import annotations

import asyncio
import json
import os
import signal
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

    process_kwargs = {
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
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
        process_kwargs["stdin"] = asyncio.subprocess.PIPE
        stdin_payload = bootstrap.encode("utf-8")
    else:
        process_kwargs["start_new_session"] = True

    process = await asyncio.create_subprocess_exec(
        *command,
        **process_kwargs,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=stdin_payload),
            timeout=settings.freecad_timeout,
        )
    except asyncio.TimeoutError as exc:
        _terminate_process(process)
        raise FreeCadParserError(f"FreeCAD parser timed out after {settings.freecad_timeout}s") from exc

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


def _terminate_process(process: asyncio.subprocess.Process) -> None:
    try:
        if os.name != "nt" and process.pid:
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
