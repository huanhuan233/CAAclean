"""Real OCCT construction parameters, independent of the tube analyzer."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


@pytest.mark.asyncio
async def test_straight_hollow_tube_is_distinct_from_rod_and_drilled_block(tmp_path: Path):
    if os.environ.get("P7_LIVE_FREECAD") != "1":
        pytest.skip("set P7_LIVE_FREECAD=1")
    settings = Settings()
    fixture = tmp_path / "tube_fixture.py"
    fixture.write_text("""
import json, sys
from pathlib import Path
import FreeCAD, Part
job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
root = Path(job['directory'])
outer = Part.makeCylinder(8, 80)
inner = Part.makeCylinder(6, 80)
tube = outer.cut(inner)
tube.exportBrep(str(root / 'tube.brep'))
rotated = tube.copy()
rotated.Placement = FreeCAD.Placement(FreeCAD.Vector(22, 7, 10), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), FreeCAD.Vector(0, 0, -1)))
rotated.exportBrep(str(root / 'rotated.brep'))
outer.exportBrep(str(root / 'rod.brep'))
Part.makeBox(30, 30, 80, FreeCAD.Vector(-15, -15, 0)).cut(inner).exportBrep(str(root / 'block.brep'))
Path(job['result_json_path']).write_text('{"status":"success"}', encoding='utf-8')
""", encoding="utf-8")
    await run_freecad_job(fixture, {"directory": str(tmp_path)}, tmp_path / "fixture-job", settings)
    result = await run_freecad_job(Path(settings.cad_script_dir) / "tube_geometry.py",
                                   {"solids": [{"solid_id": name, "asset_path": str(tmp_path / (name + ".brep"))}
                                               for name in ("tube", "rotated", "rod", "block")], "tolerance_mm": 0.01},
                                   tmp_path / "analysis-job", settings)
    assert result["status"] == "success", result
    by_id = {row["solid_id"]: row for row in result["records"]}
    tube = by_id["tube"]
    assert tube["status"] == "confirmed_straight_hollow_tube"
    assert tube["source"] == "derived_geometry"
    assert tube["section"]["outer_diameter_mm"] == pytest.approx(16)
    assert tube["section"]["inner_diameter_mm"] == pytest.approx(12)
    assert tube["section"]["wall_thickness_mm"] == pytest.approx(2)
    assert tube["path"]["length_mm"] == pytest.approx(80)
    assert len(tube["ends"]) == 2 and all(end["kind"] == "flat" for end in tube["ends"])
    assert by_id["rotated"]["status"] == "confirmed_straight_hollow_tube"
    assert by_id["rotated"]["path"]["length_mm"] == pytest.approx(80)
    assert by_id["rod"]["status"] != "confirmed_straight_hollow_tube"
    assert by_id["block"]["status"] != "confirmed_straight_hollow_tube"
