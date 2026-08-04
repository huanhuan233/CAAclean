import asyncio
import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from app.cad import parser_runner
from app.cad.parser_runner import FreeCadParserError, run_freecad_parser
from app.core.config import Settings


@pytest.mark.asyncio
async def test_runner_rejects_missing_parser_script(tmp_path):
    source = tmp_path / "part.stp"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    settings = Settings(
        freecad_cmd="freecadcmd",
        cad_script_dir=tmp_path / "missing-scripts",
        cad_work_dir=tmp_path,
    )

    with pytest.raises(FreeCadParserError, match="parser script not found"):
        await run_freecad_parser(source, uuid4(), tmp_path, settings)


@pytest.mark.asyncio
async def test_runner_invokes_freecad_without_shell_true(tmp_path, monkeypatch):
    source = tmp_path / "part.stp"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    (script_dir / "parse_step.py").write_text("# parser", encoding="utf-8")
    revision_id = uuid4()
    captured = {}

    class FakeProcess:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            captured["stdin"] = input
            if captured["args"][1] == "-c":
                text = input.decode("utf-8")
                marker = "sys.argv=[r'"
                job_path = Path(text.split(marker, 1)[1].split("', r'", 1)[1].split("'];", 1)[0])
            else:
                job_path = Path(captured["args"][2])
            job = json.loads(job_path.read_text(encoding="utf-8"))
            result_path = Path(job["result_json_path"])
            result_path.write_text(
                json.dumps(
                    {
                        "revision_id": str(revision_id),
                        "parser_name": "FreeCAD",
                        "parser_version": "test",
                        "schema_version": "1",
                        "summary": {},
                        "entities": [],
                        "relations": [],
                        "meshes": [],
                        "parse_manifest": {},
                    }
                ),
                encoding="utf-8",
            )
            return b"ok", b""

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        lambda *args, **kwargs: (_ for _ in ()).throw(NotImplementedError()),
    )
    freecad_cmd = tmp_path / "env" / "Library" / "bin" / "freecadcmd.exe"
    settings = Settings(
        freecad_cmd=str(freecad_cmd),
        cad_script_dir=script_dir,
        cad_work_dir=tmp_path,
        freecad_timeout=5,
    )

    result = await run_freecad_parser(source, revision_id, tmp_path, settings)

    assert result["parser_name"] == "FreeCAD"
    assert captured["args"][0] == str(freecad_cmd)
    assert str(script_dir / "parse_step.py") in (captured["stdin"] or b"").decode("utf-8") or captured["args"][1] == str(script_dir / "parse_step.py")
    assert f"sys.path.insert(0, r'{script_dir}')" in (captured["stdin"] or b"").decode("utf-8")
    assert "shell" not in captured["kwargs"]
    assert captured["kwargs"]["stdout"] == subprocess.PIPE
    assert captured["kwargs"]["stderr"] == subprocess.PIPE
    conda_prefix = freecad_cmd.parents[2]
    expected_paths = [
        conda_prefix,
        conda_prefix / "Library" / "mingw-w64" / "bin",
        conda_prefix / "Library" / "usr" / "bin",
        conda_prefix / "Library" / "bin",
        conda_prefix / "Scripts",
        conda_prefix / "bin",
    ]
    assert captured["kwargs"]["env"]["PATH"].split(parser_runner.os.pathsep)[:6] == [
        str(path) for path in expected_paths
    ]


@pytest.mark.asyncio
async def test_runner_times_out_and_terminates_freecad(tmp_path, monkeypatch):
    source = tmp_path / "part.stp"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    (script_dir / "parse_step.py").write_text("# parser", encoding="utf-8")
    terminated = {}

    class SlowProcess:
        pid = 12345
        returncode = None
        calls = 0

        def communicate(self, input=None, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(cmd="freecadcmd-test", timeout=timeout)
            return b"", b""

        def terminate(self):
            terminated["called"] = True

    def fake_popen(args, **kwargs):
        return SlowProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(parser_runner.os, "name", "nt")
    settings = Settings(
        freecad_cmd="freecadcmd-test",
        cad_script_dir=script_dir,
        cad_work_dir=tmp_path,
        freecad_timeout=1,
    )

    with pytest.raises(FreeCadParserError, match="timed out"):
        await run_freecad_parser(source, uuid4(), tmp_path, settings)

    assert terminated["called"] is True


@pytest.mark.asyncio
async def test_runner_reports_console_output_when_result_is_missing(tmp_path, monkeypatch):
    source = tmp_path / "part.stp"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    (script_dir / "parse_step.py").write_text("# parser", encoding="utf-8")

    class FakeProcess:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return b">>> Traceback: undefined curve type", b""

    monkeypatch.setattr(subprocess, "Popen", lambda args, **kwargs: FakeProcess())
    settings = Settings(
        freecad_cmd="freecadcmd-test",
        cad_script_dir=script_dir,
        cad_work_dir=tmp_path,
        freecad_timeout=1,
    )

    with pytest.raises(FreeCadParserError) as exc_info:
        await run_freecad_parser(source, uuid4(), tmp_path, settings)

    message = str(exc_info.value)
    assert "did not produce result.json" in message
    assert "undefined curve type" in message
