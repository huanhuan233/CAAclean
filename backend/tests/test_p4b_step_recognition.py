"""Geometric thin-wall facts remain valid while structural roles need review."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _build(path: Path, tmp_path: Path):
    cmd = os.environ.get("FREECAD_CMD")
    if not cmd or not Path(cmd).is_file():
        pytest.skip("FreeCADCmd unavailable: exact same-Solid material tests not run")
    output = tmp_path / path.stem
    process = subprocess.run([sys.executable, "-m", "scripts.feature_center", "build",
                              "--step", str(path), "--output", str(output)],
                             cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
                             text=True, capture_output=True, timeout=90)
    assert process.returncode == 0, process.stderr
    return output, [json.loads(line) for line in (output / "canonical_features.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize(("fixture", "expected"), [
    ("straight_rib", {"boss", "rib"}),
    ("thin_plate", {"web"}),
    ("tee_flange", {"web", "flange"}),
])
def test_thin_wall_structural_candidates(fixture: str, expected: set[str], tmp_path: Path) -> None:
    output, features = _build(ROOT / "backend" / "tests" / "fixtures" / "p4" / f"{fixture}.stp", tmp_path)
    assert {feature["family"] for feature in features} == expected
    measurements = [json.loads(line) for line in (output / "measurements.jsonl").read_text(encoding="utf-8").splitlines()]
    for feature in features:
        if feature["family"] == "boss":
            continue
        assert feature["review_state"] == "needs_review"
        payload = feature["typed_payload"]["geometry_recognition"]
        assert payload["local_thickness_mm"] == pytest.approx(3)
        assert payload["geometry_form_status"] == "confirmed"
        assert payload["structural_role_status"] == "candidate"
        assert feature["diagnostics"]
        thickness = next(measure for measure in measurements
                         if measure["feature_center_id"] == feature["feature_center_id"]
                         and measure["name"] == "local_thickness")
        assert thickness["value"] == pytest.approx(3)
        assert thickness["validity"] == "valid"
    if fixture == "straight_rib":
        rib = next(feature for feature in features if feature["family"] == "rib")
        payload = rib["typed_payload"]["geometry_recognition"]
        assert payload["length_mm"] == pytest.approx(50)
        assert payload["height_mm"] == pytest.approx(10)
        assert any(relation["kind"] == "STRUCTURAL_ROLE_OF" for relation in rib["relations"])
    if fixture == "tee_flange":
        flange = next(feature for feature in features if feature["family"] == "flange")
        assert flange["typed_payload"]["geometry_recognition"]["width_mm"] == pytest.approx(12)


def test_thick_block_is_not_structural_thin_wall(tmp_path: Path) -> None:
    _, features = _build(ROOT / "backend" / "tests" / "fixtures" / "p3" / "block.stp", tmp_path)
    assert not {"rib", "web", "flange"}.intersection(feature["family"] for feature in features)
