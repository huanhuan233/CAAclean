"""P4C roles and distances use existing bounded features, not names or mesh."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.feature_center.combined_measurements import _boss_rib_distance, apply_combined_measurements


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


def test_positive_sub_tolerance_gap_keeps_measured_value() -> None:
    boss = SimpleNamespace(
        subtype="circular_straight_wall", geometry_refs=SimpleNamespace(solid_ids=["S"]),
        coordinate_frame={"normal": [0, 0, 1]},
        typed_payload={"geometry_recognition": {"support_face_id": "SUP", "cap_face_id": "CAP",
                                                "diameter_mm": 10, "height_mm": 5}})
    rib = SimpleNamespace(
        family="rib", geometry_refs=SimpleNamespace(solid_ids=["S"]),
        coordinate_frame={"origin_mm": [15.0005, 0, 5], "x_axis": [1, 0, 0],
                          "y_axis": [0, 1, 0], "normal": [0, 0, 1]},
        typed_payload={"geometry_recognition": {"root_support_face_id": "SUP",
                                                "parent_geometry_feature_id": "PARENT",
                                                "length_mm": 20, "local_thickness_mm": 3,
                                                "height_mm": 5}})
    graph = SimpleNamespace(entities={"CAP": {"center": [0, 0, 5]}})
    measured = _boss_rib_distance(boss, rib, graph, 0.001)
    assert measured["distance_mm"] == pytest.approx(0.0005)
    assert measured["within_tolerance"] is True
    assert measured["intersection_status"] == "not_evaluated"
    assert measured["status"] == "measured"
    assert measured["start_point_mm"] == pytest.approx([5, 0, 2.5])
    assert measured["end_point_mm"] == pytest.approx([5.0005, 0, 2.5])


@pytest.mark.parametrize(("rib_center", "x_axis", "y_axis", "expected", "status", "near"), [
    ([16, 0, 5], [1, 0, 0], [0, 1, 0], 1.0, "measured", False),
    ([15, 0, 5], [1, 0, 0], [0, 1, 0], 0.0, "measured", True),
    ([14, 0, 5], [1, 0, 0], [0, 1, 0], 0.0, "proxy_overlap_unverified", True),
    ([0, 15.0005, 5], [0, 1, 0], [-1, 0, 0], 0.0005, "measured", True),
])
def test_gap_relation_keeps_value_separate_from_proximity_and_topology(
        rib_center, x_axis, y_axis, expected, status, near) -> None:
    boss = SimpleNamespace(
        subtype="circular_straight_wall", geometry_refs=SimpleNamespace(solid_ids=["S"]),
        coordinate_frame={"normal": [0, 0, 1]},
        typed_payload={"geometry_recognition": {"support_face_id": "SUP", "cap_face_id": "CAP",
                                                "diameter_mm": 10, "height_mm": 5}})
    rib = SimpleNamespace(
        family="rib", geometry_refs=SimpleNamespace(solid_ids=["S"]),
        coordinate_frame={"origin_mm": rib_center, "x_axis": x_axis,
                          "y_axis": y_axis, "normal": [0, 0, 1]},
        typed_payload={"geometry_recognition": {"root_support_face_id": "SUP",
                                                "parent_geometry_feature_id": "PARENT",
                                                "length_mm": 20, "local_thickness_mm": 3,
                                                "height_mm": 5}})
    measured = _boss_rib_distance(boss, rib, SimpleNamespace(entities={"CAP": {"center": [0, 0, 5]}}), 0.001)
    assert measured["distance_mm"] == pytest.approx(expected)
    assert measured["within_tolerance"] is near
    assert measured["intersection_status"] == "not_evaluated"
    assert measured["status"] == status
    if status == "proxy_overlap_unverified":
        assert measured["signed_proxy_clearance_mm"] == pytest.approx(-1)
        assert "start_point_mm" not in measured


def test_irrelevant_bosses_do_not_exhaust_relation_budget() -> None:
    def boss(index: int, support: str, solid: str = "S"):
        return SimpleNamespace(
            feature_center_id=f"B{index:03d}", family="boss", subtype="circular_straight_wall",
            geometry_refs=SimpleNamespace(solid_ids=[solid], face_ids=[]),
            coordinate_frame={"normal": [0, 0, 1]},
            typed_payload={"geometry_recognition": {"support_face_id": support,
                                                    "cap_face_id": f"CAP{index}",
                                                    "diameter_mm": 10, "height_mm": 5}})
    bosses = ([boss(index, "OTHER") for index in range(64)] +
              [boss(index, "SUP", "OTHER_SOLID") for index in range(64, 128)] +
              [boss(128, "SUP")])
    rib = SimpleNamespace(
        feature_center_id="R", family="rib", subtype="straight_prismatic_candidate",
        geometry_refs=SimpleNamespace(solid_ids=["S"], face_ids=[]),
        coordinate_frame={"origin_mm": [40, 0, 5], "x_axis": [1, 0, 0],
                          "y_axis": [0, 1, 0], "normal": [0, 0, 1]},
        relations=[],
        typed_payload={"geometry_recognition": {"root_support_face_id": "SUP",
                                                "parent_geometry_feature_id": "PARENT",
                                                "length_mm": 20, "local_thickness_mm": 3,
                                                "height_mm": 5}})
    graph = SimpleNamespace(relations=[], entities={f"CAP{i}": {"center": [0, 0, 5]}
                                                  for i in range(129)})
    result = SimpleNamespace(canonical_features=bosses+[rib], measurements=[], diagnostics=[])
    apply_combined_measurements(result, graph, 0.001)
    combined = rib.typed_payload["geometry_recognition"]["combined_measurements"]
    assert len(combined) == 1
    assert combined[0]["boss_feature_id"] == "B128"


def test_budget_records_unevaluated_relevant_bosses_and_is_order_stable() -> None:
    def run(reverse: bool):
        bosses = []
        centers = {}
        for index in range(130):
            feature_id = f"B{index:03d}"
            centers[f"CAP{index}"] = {"center": [100+index, 0, 5]}
            bosses.append(SimpleNamespace(
                feature_center_id=feature_id, family="boss", subtype="circular_straight_wall",
                geometry_refs=SimpleNamespace(solid_ids=["S"], face_ids=[]),
                coordinate_frame={"normal": [0, 0, 1]},
                typed_payload={"geometry_recognition": {"support_face_id": "SUP",
                                                        "cap_face_id": f"CAP{index}",
                                                        "diameter_mm": 10, "height_mm": 5}}))
        rib = SimpleNamespace(
            feature_center_id="R", family="rib", subtype="straight_prismatic_candidate",
            geometry_refs=SimpleNamespace(solid_ids=["S"], face_ids=[]), relations=[],
            coordinate_frame={"origin_mm": [0, 0, 5], "x_axis": [1, 0, 0],
                              "y_axis": [0, 1, 0], "normal": [0, 0, 1]},
            typed_payload={"geometry_recognition": {"root_support_face_id": "SUP",
                                                    "parent_geometry_feature_id": "PARENT",
                                                    "length_mm": 20, "local_thickness_mm": 3,
                                                    "height_mm": 5}})
        result = SimpleNamespace(canonical_features=(list(reversed(bosses)) if reverse else bosses)+[rib],
                                 measurements=[], diagnostics=[])
        apply_combined_measurements(result, SimpleNamespace(relations=[], entities=centers), 0.001)
        return rib.typed_payload["geometry_recognition"], result.diagnostics

    forward, diagnostics = run(False)
    backward, _ = run(True)
    assert forward["combined_measurement_status"] == "budget_exceeded"
    assert forward["combined_measurement_diagnostics"]["candidate_total"] == 130
    assert forward["combined_measurement_diagnostics"]["evaluated_count"] == 128
    assert forward["combined_measurement_diagnostics"]["unevaluated_count"] == 2
    assert [item["boss_feature_id"] for item in forward["combined_measurements"]] == [
        item["boss_feature_id"] for item in backward["combined_measurements"]]
    assert [item["boss_feature_id"] for item in forward["combined_measurements"]][-1] == "B127"
    assert any(item["code"] == "COMBINED_MEASUREMENT_BUDGET_EXCEEDED" for item in diagnostics)
