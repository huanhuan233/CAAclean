"""P4C roles and distances use existing bounded features, not names or mesh."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.feature_center.combined_measurements import _boss_rib_distance


ROOT = Path(__file__).resolve().parents[2]


def _bundle(name: str, tmp_path: Path):
    executable = os.environ.get("FREECAD_CMD")
    if not executable or not Path(executable).is_file():
        pytest.skip("FreeCADCmd unavailable: P4C kernel integration not run")
    output = tmp_path / name
    process = subprocess.run(
        [sys.executable, "-m", "scripts.feature_center", "build", "--step",
         str(ROOT / "backend" / "tests" / "fixtures" / "p4" / f"{name}.stp"),
         "--output", str(output)], cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
        capture_output=True, text=True, timeout=90,
    )
    assert process.returncode == 0, process.stderr
    def records(filename):
        return [json.loads(line) for line in (output / filename).read_text(encoding="utf-8").splitlines()]
    return output, records("canonical_features.jsonl"), records("measurements.jsonl")


def test_inner_bottom_fillet_is_transition_not_false_hole(tmp_path: Path) -> None:
    output, features, measures = _bundle("pocket_bottom_fillet", tmp_path)
    assert [(feature["family"], feature["subtype"]) for feature in features] == [
        ("fillet", "constant_radius_straight_edge")]
    feature = features[0]
    payload = feature["typed_payload"]["geometry_recognition"]
    assert payload["radius_mm"] == pytest.approx(2)
    assert payload["convexity"] == "concave"
    assert payload["cavity_role"] == "inner_bottom_fillet_candidate"
    assert payload["cavity_role_status"] == "candidate"
    assert payload["center_path_length_mm"] == pytest.approx(16)
    assert payload["center_path_length_definition"] == "analytic_cylinder_axis_between_bounded_transition_ends"
    assert any(measure["name"] == "center_path_length" and measure["value"] == pytest.approx(16)
               for measure in measures)
    mapping = json.loads((output / "lightweight" / "feature_mesh_map.json").read_text(encoding="utf-8"))
    assert mapping["features"][feature["feature_center_id"]]["face_ids"] == payload["transition_face_ids"]


def test_boss_to_rib_body_distance_has_real_witness_points(tmp_path: Path) -> None:
    _, features, measures = _bundle("boss_rib_distance", tmp_path)
    assert sorted(feature["family"] for feature in features) == ["boss", "boss", "rib"]
    rib = next(feature for feature in features if feature["family"] == "rib")
    combined = rib["typed_payload"]["geometry_recognition"]["combined_measurements"]
    assert len(combined) == 1
    item = combined[0]
    assert item["status"] == "measured"
    assert item["distance_mm"] == pytest.approx(20)
    assert item["start_point_mm"] == pytest.approx([20, 30, 34])
    assert item["end_point_mm"] == pytest.approx([40, 30, 34])
    assert any(measure["name"] == "boss_to_rib_shortest_distance" and
               measure["value"] == pytest.approx(20) and measure["validity"] == "valid"
               for measure in measures)


def test_boss_rib_distance_rejects_disjoint_height_ranges() -> None:
    boss = SimpleNamespace(
        subtype="circular_straight_wall", geometry_refs=SimpleNamespace(solid_ids=["S"]),
        coordinate_frame={"normal": [0, 0, 1]},
        typed_payload={"geometry_recognition": {"support_face_id": "SUP", "cap_face_id": "CAP",
                                                "diameter_mm": 10, "height_mm": 5}})
    rib = SimpleNamespace(
        family="rib", geometry_refs=SimpleNamespace(solid_ids=["S"]),
        coordinate_frame={"origin_mm": [40, 0, 20], "x_axis": [1, 0, 0],
                          "y_axis": [0, 1, 0], "normal": [0, 0, 1]},
        typed_payload={"geometry_recognition": {"root_support_face_id": "SUP",
                                                "parent_geometry_feature_id": "PARENT",
                                                "length_mm": 20, "local_thickness_mm": 3,
                                                "height_mm": 5}})
    graph = SimpleNamespace(entities={"CAP": {"center": [0, 0, 5]}})
    assert _boss_rib_distance(boss, rib, graph, 1e-5) is None
