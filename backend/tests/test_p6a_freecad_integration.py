"""Opt-in exact kernel test with construction parameters independent of the analyzer."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


@pytest.mark.asyncio
async def test_p6a_world_placed_boxes_gap_contact_and_interference(tmp_path: Path):
    if os.environ.get("P6_LIVE_FREECAD") != "1":
        pytest.skip("set P6_LIVE_FREECAD=1 to run real FreeCAD B-Rep kernel")
    settings = Settings()
    fixture = tmp_path / "build_boxes.py"
    fixture.write_text("""
import json, sys
from pathlib import Path
import FreeCAD, Part
job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for name, x in [('A', 0.0), ('GAP', 10.001), ('TOUCH', 10.0), ('OVERLAP', 9.5)]:
    Part.makeBox(10, 10, 10, FreeCAD.Vector(x, 0, 0)).exportBrep(str(Path(job['directory']) / (name + '.brep')))
Path(job['result_json_path']).write_text('{"status":"success"}', encoding='utf-8')
""", encoding="utf-8")
    await run_freecad_job(fixture, {"directory": str(tmp_path)}, tmp_path / "fixture-job", settings)
    pairs = [
        ("A", "GAP", 0.001, "positive_gap"),
        ("A", "TOUCH", 0.0, "face_contact"),
        ("A", "OVERLAP", 0.0, "interference"),
    ]
    for left, right, expected_distance, expected_kind in pairs:
        result = await run_freecad_job(
            Path(settings.cad_script_dir) / "assembly_relations.py",
            {"instances": [{"instance_id": name, "solid_id": name,
                            "asset_path": str(tmp_path / (name + ".brep")),
                            "coordinate_convention": "world_placed_step"} for name in (left, right)],
             "candidate_distance_mm": 100, "tolerance_mm": 0.01},
            tmp_path / f"query-{right}", settings)
        assert result["status"] == "success", result
        relation = result["relations"][0]
        assert relation["distance_mm"] == pytest.approx(expected_distance, abs=1e-6)
        assert relation["contact_kind"] == expected_kind, relation
        if expected_distance > 0:
            assert relation["intersection_status"] != "positive_volume"
