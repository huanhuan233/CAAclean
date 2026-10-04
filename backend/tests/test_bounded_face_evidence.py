"""Trimmed planar faces reject holes and concave bbox false positives."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


@pytest.mark.asyncio
async def test_exact_trimmed_face_point_membership(tmp_path: Path) -> None:
    script_dir = Path(__file__).resolve().parents[1] / "freecad_scripts"
    settings = Settings(cad_script_dir=script_dir, freecad_timeout=60)
    if not (Path(settings.freecad_cmd).is_file() or shutil.which(settings.freecad_cmd)):
        pytest.skip("FreeCADCmd unavailable")
    result = await run_freecad_job(script_dir / "probe_bounded_face_cases.py", {}, tmp_path, settings)
    assert {name: item["status"] for name, item in result.items()} == {
        "annular_hole": "outside", "annular_boundary": "boundary", "annular_material": "inside",
        "offset_hole": "outside", "concave_outside": "outside", "concave_inside": "inside",
        "complete_disc": "inside",
    }
