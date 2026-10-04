from __future__ import annotations

import hashlib

import pytest

from app.assembly.context import AssemblyContextError, resolve_occurrence_matrix, step_world_solids
from app.measurement.geometry_snapshot import GeometrySnapshot


def test_world_placed_step_objects_resolve_distinct_solid_assets(tmp_path):
    assets = {}
    for solid_id, object_id in (("S1", "OBJ1"), ("S2", "OBJ2"), ("S3", "OBJ1")):
        path = tmp_path / f"{solid_id}.brep"
        path.write_bytes(solid_id.encode())
        assets[solid_id] = {"kind": "solid", "path": path.name,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "source_object_id": object_id,
                            "coordinate_convention": "world_placed_step"}
    snapshot = GeometrySnapshot(tmp_path, "REV", "SNAP", assets)
    solids = step_world_solids(snapshot)
    assert [(item.instance_id, item.solid_id) for item in solids] == [
        ("OBJ1", "S1"), ("OBJ2", "S2"), ("OBJ1", "S3")]
    assert solids[0].asset_path == str(tmp_path / "S1.brep")
    with pytest.raises(AssemblyContextError, match="selected instance"):
        step_world_solids(snapshot, {"OBJ1", "missing"})


def test_legacy_or_merged_geometry_cannot_be_claimed_as_instance_mapping(tmp_path):
    path = tmp_path / "solid.brep"
    path.write_bytes(b"solid")
    snapshot = GeometrySnapshot(tmp_path, "REV", "SNAP", {
        "S1": {"kind": "solid", "path": path.name,
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}})
    with pytest.raises(AssemblyContextError, match="mapping_unavailable"):
        step_world_solids(snapshot)


def test_absolute_occurrence_matrix_is_not_composed_twice():
    parent = [[1, 0, 0, 10], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    absolute = [[1, 0, 0, 15], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    row = {"transform_status": "resolved_absolute", "transform_4x4": sum(absolute, [])}
    assert resolve_occurrence_matrix(row, parent)[0][3] == 15
    relative = {"transform_status": "resolved_parent_relative", "transform_4x4": sum(
        [[1, 0, 0, 5], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], [])}
    assert resolve_occurrence_matrix(relative, parent)[0][3] == 15
    with pytest.raises(AssemblyContextError, match="parent"):
        resolve_occurrence_matrix(relative)


def test_reflection_is_rejected_before_instance_distance():
    reflected = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    with pytest.raises(AssemblyContextError, match="reflection"):
        resolve_occurrence_matrix({"transform_status": "resolved_absolute", "transform_4x4": sum(reflected, [])})
