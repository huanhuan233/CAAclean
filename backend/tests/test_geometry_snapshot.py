from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.measurement.geometry_snapshot import GeometryReferenceError, GeometrySnapshot, transform_geometry, validate_query


def test_snapshot_rejects_stale_and_unmapped_refs(tmp_path: Path):
    asset = tmp_path / "face.brep"
    asset.write_bytes(b"brep data")
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    snapshot = GeometrySnapshot(
        root=tmp_path,
        revision_id="revision-a",
        snapshot_id="snapshot-a",
        assets={"FACE1": {"kind": "face", "path": "face.brep", "sha256": digest}},
    )
    assert snapshot.resolve({"revision_id": "revision-a", "geometry_snapshot_id": "snapshot-a", "entity_id": "FACE1"}) == asset
    with pytest.raises(GeometryReferenceError, match="stale_reference"):
        snapshot.resolve({"revision_id": "revision-a", "geometry_snapshot_id": "old", "entity_id": "FACE1"})
    with pytest.raises(GeometryReferenceError, match="geometry_unavailable"):
        snapshot.resolve({"revision_id": "revision-a", "geometry_snapshot_id": "snapshot-a", "entity_id": "FACE2"})
    asset.write_bytes(b"replaced")
    with pytest.raises(GeometryReferenceError, match="stale_reference"):
        snapshot.resolve({"revision_id": "revision-a", "geometry_snapshot_id": "snapshot-a", "entity_id": "FACE1"})


def test_points_vectors_normals_and_invalid_transforms():
    rotation_translation = [[0, -1, 0, 10], [1, 0, 0, 20], [0, 0, 1, 30], [0, 0, 0, 1]]
    assert transform_geometry([2, 3, 4], rotation_translation, "point") == pytest.approx([7, 22, 34])
    assert transform_geometry([2, 3, 4], rotation_translation, "vector") == pytest.approx([-3, 2, 4])
    assert transform_geometry([1, 0, 0], rotation_translation, "normal") == pytest.approx([0, 1, 0])
    with pytest.raises(ValueError, match="reflection"):
        transform_geometry([1, 0, 0], [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], "point")
    with pytest.raises(ValueError, match="non_rigid"):
        transform_geometry([1, 0, 0], [[2, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], "point")


def test_query_contract_rejects_fallback_and_wrong_arity():
    with pytest.raises(ValueError, match="unsupported"):
        validate_query("distance", [{"entity_id": "A"}, {"entity_id": "B"}], {}, "native_only")
    with pytest.raises(ValueError, match="invalid_input"):
        validate_query("distance", [{"entity_id": "A"}], {}, "auxiliary_brep")
    with pytest.raises(ValueError, match="invalid_input"):
        validate_query("section", [{"entity_id": "S"}], {"origin": [0, 0, 0], "normal": [0, 0, 0]}, "auxiliary_brep")
    assert validate_query("distance", [{"entity_id": "A"}, {"entity_id": "B"}], {}, "auxiliary_brep") == "distance"
