from __future__ import annotations

import math
import shutil
from pathlib import Path

import pytest

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


@pytest.mark.asyncio
async def test_real_brep_queries_cover_finite_distance_section_and_material_thickness(tmp_path: Path):
    settings = Settings(cad_script_dir=Path(__file__).resolve().parents[1] / "freecad_scripts", freecad_timeout=60)
    if not (Path(settings.freecad_cmd).is_file() or shutil.which(settings.freecad_cmd)):
        pytest.skip("FreeCADCmd unavailable")
    script_dir = Path(settings.cad_script_dir)
    fixture_dir = tmp_path / "fixtures"
    await run_freecad_job(script_dir / "create_geometry_query_fixtures.py",
                          {"fixture_dir": str(fixture_dir)}, tmp_path / "generate", settings)

    async def query(operation, names, kinds, parameters=None):
        return await run_freecad_job(script_dir / "measure_geometry.py", {
            "operation": operation,
            "asset_paths": [str(fixture_dir / (name + ".brep")) for name in names],
            "asset_kinds": kinds,
            "parameters": parameters or {}, "tolerance_mm": 0.0001,
        }, tmp_path / ("query-" + operation + "-" + "-".join(names)), settings)

    points = await query("distance", ["point_a", "point_b"], ["vertex", "vertex"])
    assert points["status"] == "success"
    assert points["values"]["distance_mm"] == pytest.approx(5.0)
    finite_edge = await query("distance", ["finite_edge", "edge_point"], ["edge", "vertex"])
    assert finite_edge["values"]["distance_mm"] == pytest.approx(math.sqrt(5))
    assert finite_edge["values"]["nearest_points"][0]["a"] == pytest.approx([1, 0, 0])
    finite_face = await query("distance", ["plate_top", "point_outside"], ["face", "vertex"])
    assert finite_face["values"]["distance_mm"] == pytest.approx(10.0)
    right_angle = await query("angle", ["edge_x", "edge_y"], ["edge", "edge"], {"orientation": "unoriented"})
    assert right_angle["values"]["angle_deg"] == pytest.approx(90.0)
    section = await query("section", ["perforated"], ["solid"], {"origin": [10, 5, 2], "normal": [0, 0, 1]})
    assert section["status"] == "success"
    assert section["values"]["net_area_mm2"] == pytest.approx(200 - 4 * math.pi, rel=1e-5)
    assert section["values"]["regions"][0]["boundary_count"] == 2
    plate_wall = await query("local_thickness", ["plate_top", "plate"], ["face", "solid"], {"point": [2, 2, 4]})
    assert plate_wall["values"]["local_normal_thickness_mm"] == pytest.approx(4, abs=0.001)
    cavity_wall = await query("local_thickness", ["hollow_top", "hollow"], ["face", "solid"], {"point": [5, 5, 10]})
    assert cavity_wall["values"]["local_normal_thickness_mm"] == pytest.approx(2, abs=0.001)
