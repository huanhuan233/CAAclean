"""Real OCC smoke with independent synthetic plate construction parameters."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


@pytest.mark.asyncio
async def test_lap_classification_and_explicit_boolean(tmp_path: Path):
    if os.environ.get("P6_LIVE_FREECAD") != "1":
        pytest.skip("set P6_LIVE_FREECAD=1")
    settings = Settings()
    fixture = tmp_path / "plates.py"
    fixture.write_text("""
import json, sys
from pathlib import Path
import FreeCAD, Part
job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
Part.makeBox(20,20,2,FreeCAD.Vector(0,0,0)).exportBrep(job['left'])
Part.makeBox(20,20,2,FreeCAD.Vector(5,0,2)).exportBrep(job['right'])
Part.makeBox(20,20,2,FreeCAD.Vector(20,0,0)).exportBrep(job['butt'])
Path(job['result_json_path']).write_text('{"status":"success"}', encoding='utf-8')
""", encoding="utf-8")
    left, right = tmp_path / "left.brep", tmp_path / "right.brep"
    butt = tmp_path / "butt.brep"
    await run_freecad_job(fixture, {"left": str(left), "right": str(right), "butt": str(butt)}, tmp_path / "fixture", settings)
    script_dir = Path(settings.cad_script_dir)
    relations = await run_freecad_job(script_dir / "assembly_relations.py", {
        "instances": [{"instance_id": "A", "solid_id": "S1", "asset_path": str(left),
                       "coordinate_convention": "world_placed_step"},
                      {"instance_id": "B", "solid_id": "S2", "asset_path": str(right),
                       "coordinate_convention": "world_placed_step"}],
        "candidate_distance_mm": 1, "tolerance_mm": 0.001, "minimum_lap_fraction": 0.5,
    }, tmp_path / "relation-job", settings)
    record = relations["relations"][0]
    assert record["contact_kind"] == "face_contact"
    assert record["joint_classification"]["status"] == "confirmed"
    assert record["joint_classification"]["joint_kind"] == "lap"
    assert record["joint_classification"]["overlap_fraction"] == pytest.approx(0.75)
    butt_relation = await run_freecad_job(script_dir / "assembly_relations.py", {
        "instances": [{"instance_id": "A", "solid_id": "S1", "asset_path": str(left),
                       "coordinate_convention": "world_placed_step"},
                      {"instance_id": "C", "solid_id": "S3", "asset_path": str(butt),
                       "coordinate_convention": "world_placed_step"}],
        "candidate_distance_mm": 1, "tolerance_mm": 0.001,
    }, tmp_path / "butt-job", settings)
    butt_record = butt_relation["relations"][0]
    assert butt_record["contact_kind"] == "face_contact"
    assert butt_record["joint_classification"]["joint_kind"] == "butt"
    assert butt_record["joint_classification"]["status"] == "confirmed"
    assert butt_record["joint_classification"]["contact_area_mm2"] == pytest.approx(40)
    boolean_script = script_dir / "assembly_boolean.py"
    for operation, expected in (("union", 1600), ("difference", 800), ("intersection", 0)):
        result = await run_freecad_job(boolean_script, {
            "left_asset_path": str(left), "right_asset_path": str(right),
            "output_asset_path": str(tmp_path / f"{operation}.brep"), "operation": operation,
        }, tmp_path / f"job-{operation}", settings)
        assert result["volume_mm3"] == pytest.approx(expected)
        assert result["status"] == ("empty" if expected == 0 else "complete")
        assert left.is_file() and right.is_file()
