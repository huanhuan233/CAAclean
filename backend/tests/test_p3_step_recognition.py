"""STEP acceptance cases with independent FreeCAD construction dimensions.

The fixtures were exported from boxes of 80 x 60 x 30 mm. Cylinders and
edge treatments were constructed with the sizes asserted below. No native
CATIA feature tree or recognition output was used as an oracle.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "p3"


def _features(name: str, tmp_path: Path) -> list[dict]:
    executable = os.environ.get("FREECAD_CMD")
    if not executable or not Path(executable).is_file():
        pytest.skip("FreeCADCmd unavailable: real kernel integration not run")
    output = tmp_path / name
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.feature_center", "build",
         "--step", str(FIXTURES / f"{name}.stp"), "--output", str(output)],
        cwd=ROOT, env=environment, text=True, capture_output=True, timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    return [json.loads(line) for line in (output / "canonical_features.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize(("name", "expected"), [
    ("block", []), ("boss", []),
    ("half_slot", [("hole", "cylindrical_void_candidate")]),
    ("through", [("hole", "through_hole")]),
    ("through_m", [("hole", "through_hole")]),
    ("blind", [("hole", "blind_hole")]),
    ("conical_blind", [("hole", "blind_hole")]),
    ("shallow_large", [("hole", "blind_hole")]),
    ("step", [("hole", "stepped_through_hole")]),
    ("divider", [("hole", "blind_hole"), ("hole", "blind_hole")]),
    ("closed_cavity", [("hole", "cylindrical_void_candidate")]),
    ("fillet", [("fillet", "constant_radius_straight_edge")]),
    ("chamfer", [("chamfer", "straight_edge_two_plane")]),
    ("chamfer_unequal", [("chamfer", "straight_edge_two_plane")]),
    ("mouth_chamfer", [("hole", "through_hole"), ("chamfer", "circular_hole_mouth_cone")]),
    ("through_transformed", [("hole", "through_hole")]),
    ("two_solids", [("hole", "through_hole"), ("hole", "through_hole")]),
    ("remote_material_after_through", [("hole", "through_hole")]),
])
def test_pure_step_recognition(name: str, expected: list[tuple[str, str]], tmp_path: Path) -> None:
    features = [feature for feature in _features(name, tmp_path)
                if feature["family"] in {"hole", "fillet", "chamfer"}]
    assert sorted((feature["family"], feature["subtype"]) for feature in features) == sorted(expected)
    assert all(not feature["native_feature_ids"] for feature in features)
    assert all(feature["geometry_refs"]["face_ids"] for feature in features)
    assert all(feature["provenance"]["native_history_attribution"] == "not_evaluated" for feature in features)
    if name == "half_slot":
        assert features[0]["review_state"] == "needs_review"
    if name in {"through", "through_m"}:
        payload = features[0]["typed_payload"]["geometry_recognition"]
        assert payload["diameter_mm"] == pytest.approx(10)
        assert payload["cylindrical_wall_length_mm"] == pytest.approx(30)
    if name == "shallow_large":
        payload = features[0]["typed_payload"]["geometry_recognition"]
        assert payload["diameter_mm"] == pytest.approx(40)
        assert payload["cylindrical_wall_length_mm"] == pytest.approx(2)
    if name == "blind":
        payload = features[0]["typed_payload"]["geometry_recognition"]
        assert payload["flat_bottom_depth_mm"] == pytest.approx(15)
        assert payload["bottom_face_ids"] == [payload["end_boundary"][0]["face_id"]]
        assert payload["end_boundary"][0]["kind"] == "flat"
    if name == "conical_blind":
        payload = features[0]["typed_payload"]["geometry_recognition"]
        assert payload["cylindrical_wall_length_mm"] == pytest.approx(15)
        assert payload["total_depth_mm"] == pytest.approx(18)
        assert payload["drill_tip_face_ids"] == [payload["end_boundary"][0]["face_id"]]
    if name == "step":
        segments = features[0]["typed_payload"]["geometry_recognition"]["segments"]
        assert [item["diameter_mm"] for item in segments] == pytest.approx([10, 18])
        assert [item["cylindrical_wall_length_mm"] for item in segments] == pytest.approx([25, 5])
    if name == "fillet":
        assert features[0]["typed_payload"]["geometry_recognition"]["radius_mm"] == pytest.approx(3)
    if name in {"chamfer", "chamfer_unequal"}:
        payload = features[0]["typed_payload"]["geometry_recognition"]
        assert sorted([payload["d1_mm"], payload["d2_mm"]]) == pytest.approx([4, 4] if name == "chamfer" else [3, 6])
    if name == "mouth_chamfer":
        payload = next(feature for feature in features if feature["family"] == "chamfer")["typed_payload"]["geometry_recognition"]
        assert payload["axial_distance_mm"] == pytest.approx(2)
        assert payload["radial_distance_mm"] == pytest.approx(2)
    if name == "two_solids":
        assert len({feature["geometry_refs"]["solid_ids"][0] for feature in features}) == 2
    if name == "remote_material_after_through":
        payload = features[0]["typed_payload"]["geometry_recognition"]
        assert payload["cylindrical_wall_length_mm"] == pytest.approx(30)
        assert payload["end_states"] == ["void", "void"]
        assert payload["end_scan"][1]["first_material_offset_mm"] == pytest.approx(20)
        assert payload["end_boundary"][1]["status"] == "open"
    if name == "closed_cavity":
        payload = features[0]["typed_payload"]["geometry_recognition"]
        assert features[0]["review_state"] == "needs_review"
        assert payload["cylindrical_wall_length_mm"] == pytest.approx(14)
        assert sorted(item["kind"] for item in payload["end_boundary"]) == ["flat", "flat"]
