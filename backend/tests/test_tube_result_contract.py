from types import SimpleNamespace

import pytest

from app.assembly.context import AssemblyContextError
from app.tube.service import validate_tube_result_scope, validate_tube_dimensions


def valid_bent_record():
    return {"status": "confirmed_bent_hollow_tube", "path": {"length_mm": 50, "segments": [{"kind": "arc"}]},
            "section": {"outer_diameter_mm": 8, "inner_diameter_mm": 6, "wall_thickness_mm": 1,
                        "unit": "mm", "tolerance_mm": 0.01, "uniformity_status": "verified_analytic_constant_section",
                        "samples": [{"status": "verified", "outer_diameter_mm": 8,
                                     "inner_diameter_mm": 6, "wall_thickness_mm": 1} for _ in range(3)]}}


def test_bent_dimensions_can_be_published_with_separate_inner_outer_and_wall():
    validate_tube_dimensions(valid_bent_record())


@pytest.mark.parametrize("segment", [None, "arc", {"kind": "spline"}])
def test_malformed_segment_is_a_business_error_before_publish(segment):
    record = valid_bent_record()
    record['path']['segments'] = [segment]
    with pytest.raises(AssemblyContextError, match='geometry_result_invalid'):
        validate_tube_dimensions(record)


@pytest.mark.parametrize("key,value", [("wall_thickness_mm", float('nan')), ("wall_thickness_mm", 2),
                                      ("outer_diameter_mm", 4), ("unit", "inch"), ("samples", [])])
def test_invalid_confirmed_dimensions_are_rejected_before_publish(key, value):
    record = valid_bent_record()
    record['section'][key] = value
    with pytest.raises(AssemblyContextError, match='geometry_result_invalid'):
        validate_tube_dimensions(record)


def test_tube_result_uses_solid_identity_when_kernel_reorders_records():
    solids = [SimpleNamespace(solid_id="T", instance_id="TUBE"),
              SimpleNamespace(solid_id="N", instance_id="NEIGHBOR")]
    result = {"algorithm_version": "tube.geometry.circular.v3",
              "records": [{"solid_id": "N", "status": "unsupported_geometry"},
                          {"solid_id": "T", "status": "unsupported_geometry"}],
              "clearances": [{"tube_solid_id": "T", "target_solid_id": "N", "status": "evaluated"}]}
    records, clearances = validate_tube_result_scope(result, solids, "T")
    assert records["T"]["solid_id"] == "T"
    assert records["N"]["status"] == "unsupported_geometry"
    assert clearances[0]["target_solid_id"] == "N"


@pytest.mark.parametrize("records", [
    [{"solid_id": "T"}, {"solid_id": "T"}],
    [{"solid_id": "T"}],
    [{"solid_id": "T"}, {"solid_id": "EXTRA"}],
])
def test_tube_result_rejects_duplicate_missing_and_extra_solid_identity(records):
    solids = [SimpleNamespace(solid_id="T"), SimpleNamespace(solid_id="N")]
    with pytest.raises(AssemblyContextError, match="geometry_result_invalid"):
        validate_tube_result_scope({"algorithm_version": "tube.geometry.circular.v3",
                                    "records": records, "clearances": []}, solids, "T")
