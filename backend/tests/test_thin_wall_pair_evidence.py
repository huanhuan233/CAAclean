"""Local thickness exists despite a face centroid falling outside overlap."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


@pytest.mark.asyncio
async def test_partial_overlap_is_order_independent_and_annular_centroid_is_not_required(tmp_path: Path) -> None:
    script_dir = Path(__file__).resolve().parents[1] / "freecad_scripts"
    settings = Settings(cad_script_dir=script_dir, freecad_timeout=60)
    if not (Path(settings.freecad_cmd).is_file() or shutil.which(settings.freecad_cmd)):
        pytest.skip("FreeCADCmd unavailable")
    cases = await run_freecad_job(script_dir / "probe_thin_wall_cases.py", {}, tmp_path, settings)
    forward = cases["partial_forward"]["pairs"]
    reverse = cases["partial_reverse"]["pairs"]
    assert len(forward) == len(reverse) == 1
    assert forward[0]["thickness_mm"] == reverse[0]["thickness_mm"] == pytest.approx(6)
    assert forward[0]["pair_id"] == reverse[0]["pair_id"]
    full_a = {(pair["pair_id"], pair["thickness_mm"]) for pair in cases["full_order_a"]["pairs"]}
    full_b = {(pair["pair_id"], pair["thickness_mm"]) for pair in cases["full_order_b"]["pairs"]}
    assert full_a == full_b
    assert any(pair_id == forward[0]["pair_id"] and thickness == pytest.approx(6)
               for pair_id, thickness in full_a)
    assert len(cases["ring"]["pairs"]) == 1
    assert cases["ring"]["pairs"][0]["thickness_mm"] == pytest.approx(3)
    assert cases["air_gap"]["pairs"] == []
    assert cases["air_gap"]["status"]["status"] == "evaluated"
    assert cases["no_overlap"]["pairs"] == []
