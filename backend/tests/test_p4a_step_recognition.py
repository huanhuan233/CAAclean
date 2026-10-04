"""Independent CAD construction dimensions, not recognition-generated oracles."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "p4"


@pytest.mark.parametrize(("fixture", "family", "subtype", "dimensions"), [
    ("rect_boss", "boss", "rectangular_straight_wall", {"length_mm": 16, "width_mm": 12, "height_mm": 8}),
    ("rect_pocket", "pocket", "rectangular_straight_wall", {"length_mm": 16, "width_mm": 12, "depth_mm": 8}),
    ("open_slot", "slot", "open_straight_wall", {"length_mm": 19, "width_mm": 12, "depth_mm": 8}),
])
def test_standard_planar_structures(fixture: str, family: str, subtype: str,
                                    dimensions: dict[str, float], tmp_path: Path) -> None:
    executable = os.environ.get("FREECAD_CMD")
    if not executable or not Path(executable).is_file():
        pytest.skip("FreeCADCmd unavailable: kernel integration not run")
    output = tmp_path / fixture
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.feature_center", "build", "--step", str(FIXTURES / f"{fixture}.stp"),
         "--output", str(output)], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
        text=True, capture_output=True, timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    features = [json.loads(line) for line in (output / "canonical_features.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(item["family"], item["subtype"]) for item in features] == [(family, subtype)]
    feature = features[0]
    payload = feature["typed_payload"]["geometry_recognition"]
    for key, expected in dimensions.items():
        assert payload[key] == pytest.approx(expected)
    assert feature["review_state"] == "auto_verified"
    assert feature["coordinate_frame"]["axis_selection"] == "finite_cap_edges"
    face_map = json.loads((output / "lightweight" / "feature_mesh_map.json").read_text(encoding="utf-8"))
    display_faces = face_map["features"][feature["feature_center_id"]]["face_ids"]
    assert payload["support_face_id"] not in display_faces
    assert payload["cap_face_id"] in display_faces
    if family == "pocket":
        assert payload["bounded_cavity_volume_mm3"] == pytest.approx(16*12*8)
    if family == "slot":
        assert "bounded_cavity_volume_mm3" not in payload
        assert payload["side_opening_face_ids"]


def test_circular_boss_is_not_a_pocket(tmp_path: Path) -> None:
    executable = os.environ.get("FREECAD_CMD")
    if not executable or not Path(executable).is_file():
        pytest.skip("FreeCADCmd unavailable: kernel integration not run")
    output = tmp_path / "circular_boss"
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.feature_center", "build", "--step",
         str(ROOT / "backend" / "tests" / "fixtures" / "p3" / "boss.stp"), "--output", str(output)],
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
        text=True, capture_output=True, timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    features = [json.loads(line) for line in (output / "canonical_features.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(item["family"], item["subtype"]) for item in features] == [("boss", "circular_straight_wall")]
    payload = features[0]["typed_payload"]["geometry_recognition"]
    assert payload["diameter_mm"] == pytest.approx(16)
    assert payload["height_mm"] == pytest.approx(15)


@pytest.mark.parametrize(("fixture", "expected"), [
    ("rotated_rect_boss", {"boss": (16, 12, 8)}),
    ("multi_solid_boss_pocket", {"boss": (16, 12, 8), "pocket": (16, 12, 8)}),
])
def test_orientation_and_solid_isolation(fixture: str, expected: dict[str, tuple[float, float, float]],
                                         tmp_path: Path) -> None:
    executable = os.environ.get("FREECAD_CMD")
    if not executable or not Path(executable).is_file():
        pytest.skip("FreeCADCmd unavailable: orientation and multi-Solid integration not run")
    output = tmp_path / fixture
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.feature_center", "build", "--step", str(FIXTURES / f"{fixture}.stp"),
         "--output", str(output)], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
        text=True, capture_output=True, timeout=90)
    assert completed.returncode == 0, completed.stderr
    features = [json.loads(line) for line in (output / "canonical_features.jsonl").read_text(encoding="utf-8").splitlines()]
    structures = [feature for feature in features if feature["family"] in expected]
    assert sorted(feature["family"] for feature in structures) == sorted(expected)
    assert len({feature["geometry_refs"]["solid_ids"][0] for feature in structures}) == len(expected)
    for feature in structures:
        payload = feature["typed_payload"]["geometry_recognition"]
        length, width, extent = expected[feature["family"]]
        assert payload["length_mm"] == pytest.approx(length, abs=1e-4)
        assert payload["width_mm"] == pytest.approx(width, abs=1e-4)
        assert payload["height_mm" if feature["family"] == "boss" else "depth_mm"] == pytest.approx(extent, abs=1e-4)
