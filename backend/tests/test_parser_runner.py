import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

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

        async def communicate(self, input=None):
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

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    settings = Settings(
        freecad_cmd="freecadcmd-test",
        cad_script_dir=script_dir,
        cad_work_dir=tmp_path,
        freecad_timeout=5,
    )

    result = await run_freecad_parser(source, revision_id, tmp_path, settings)

    assert result["parser_name"] == "FreeCAD"
    assert captured["args"][0] == "freecadcmd-test"
    assert str(script_dir / "parse_step.py") in (captured["stdin"] or b"").decode("utf-8") or captured["args"][1] == str(script_dir / "parse_step.py")
    assert "shell" not in captured["kwargs"]
    assert captured["kwargs"]["stdout"] == asyncio.subprocess.PIPE
    assert captured["kwargs"]["stderr"] == asyncio.subprocess.PIPE
