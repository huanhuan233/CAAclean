"""Tube exterior clearance uses actual B-Rep surfaces and independent fixture offsets."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


@pytest.mark.asyncio
async def test_exterior_clearance_and_interference_states(tmp_path: Path):
    if os.environ.get("P7_LIVE_FREECAD") != "1":
        pytest.skip("set P7_LIVE_FREECAD=1")
    settings = Settings()
    fixture = tmp_path / "installation_fixture.py"
    fixture.write_text("""
import json, sys
from pathlib import Path
import FreeCAD, Part
job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
root = Path(job['directory'])
Part.makeCylinder(8, 80).cut(Part.makeCylinder(6, 80)).exportBrep(str(root / 'tube.brep'))
for name, x in [('gap', 10), ('micro', 8.001), ('touch', 8), ('overlap', 7.5)]:
    Part.makeBox(2, 2, 20, FreeCAD.Vector(x, -1, 30)).exportBrep(str(root / (name + '.brep')))
Path(job['result_json_path']).write_text('{"status":"success"}', encoding='utf-8')
""", encoding="utf-8")
    await run_freecad_job(fixture, {"directory": str(tmp_path)}, tmp_path / "fixture-job", settings)
    for name, expected in (("gap", 2), ("micro", 0.001), ("touch", 0), ("overlap", 0)):
        result = await run_freecad_job(
            Path(settings.cad_script_dir) / "tube_geometry.py",
            {"solids": [{"solid_id": item, "asset_path": str(tmp_path / (item + ".brep"))}
                        for item in ("tube", name)],
             "target_tube_solid_id": "tube", "tolerance_mm": 0.01},
            tmp_path / f"query-{name}", settings)
        assert result["status"] == "success", result
        assert result["diagnostics"]["loaded_shapes"] == 2
        clearance = result["clearances"][0]
        assert clearance["distance_mm"] == pytest.approx(expected, abs=1e-5)
        assert clearance["witnesses"]
        assert clearance["within_tolerance"] == (expected <= 0.01)
        if name == "overlap":
            assert clearance["intersection_status"] == "positive_volume"
        elif expected > 0:
            assert clearance["intersection_status"] != "positive_volume"
