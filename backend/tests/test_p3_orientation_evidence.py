from app.feature_center.geometry_recognition import _normalized_wall, _common_angular_bins


def _wall(axis, axial, states, scans):
    return {
        "entity_id": "FACE-X", "geometry_type": "cylinder",
        "geometry": {"center": [0, 0, 0], "radius": 5, "recognition_evidence": {
            "status": "evaluated", "axis_unit": axis, "axial_range_mm": axial,
            "angular_coverage_rad": 6.283185307179586,
            "radial_material_side": "inner_wall", "end_states": states,
            "end_scan": scans,
            "angular_sample_directions": [[1, 0, 0]],
        }},
    }


def test_reverse_axis_reverses_end_evidence_and_preserves_physical_ends():
    low = {"state": "material", "method": "exact_centerline_solid_intersection"}
    high = {"state": "void", "method": "exact_centerline_solid_intersection"}
    forward = _normalized_wall(_wall([0, 0, 1], [0, 15], ["material", "void"], [low, high]))
    reverse = _normalized_wall(_wall([0, 0, -1], [-15, 0], ["void", "material"], [high, low]))

    assert forward is not None and reverse is not None
    assert reverse["axis"] == forward["axis"]
    assert reverse["start"] == forward["start"]
    assert reverse["end"] == forward["end"]
    assert reverse["end_states"] == forward["end_states"]
    assert reverse["end_scan"] == forward["end_scan"]


def test_angular_bins_require_world_space_basis():
    wall = _normalized_wall(_wall([0, 0, 1], [0, 15], ["void", "void"], []))
    assert wall is not None
    assert len(_common_angular_bins([wall], wall["axis"])) == 1
    wall["evidence"].pop("angular_sample_directions")
    assert _common_angular_bins([wall], wall["axis"]) is None
