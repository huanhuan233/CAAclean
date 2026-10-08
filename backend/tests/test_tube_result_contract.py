from types import SimpleNamespace

import pytest

from app.assembly.context import AssemblyContextError
from app.tube.service import validate_tube_result_scope


def test_tube_result_uses_solid_identity_when_kernel_reorders_records():
    solids = [SimpleNamespace(solid_id="T", instance_id="TUBE"),
              SimpleNamespace(solid_id="N", instance_id="NEIGHBOR")]
    result = {"algorithm_version": "tube.geometry.p7c.v2",
              "records": [{"solid_id": "N", "status": "unsupported_geometry"},
                          {"solid_id": "T", "status": "confirmed_straight_hollow_tube"}],
              "clearances": [{"tube_solid_id": "T", "target_solid_id": "N", "status": "evaluated"}]}
    records, clearances = validate_tube_result_scope(result, solids, "T")
    assert records["T"]["status"] == "confirmed_straight_hollow_tube"
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
        validate_tube_result_scope({"algorithm_version": "tube.geometry.p7c.v2",
                                    "records": records, "clearances": []}, solids, "T")
