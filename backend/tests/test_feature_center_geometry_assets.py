from __future__ import annotations

from pathlib import Path

from app.feature_center.geometry_assets import attach_geometry_assets
from app.feature_center.contracts import FeatureCenterBundle
from app.feature_center.topology import StableTopology


def test_geometry_assets_bind_stable_id_to_exact_brep(tmp_path: Path):
    source_id = "source-face"
    (tmp_path / f"{source_id}.brep").write_bytes(b"exact face")
    bundle = FeatureCenterBundle(input_file_name="part.stp", input_sha256="a" * 64, shape_hash="shape")
    topology = StableTopology("shape", 0.01, [], [], {source_id: "FACE1"})
    attach_geometry_assets(bundle, topology, [{"id": source_id, "entity_type": "face"}], tmp_path)
    assert bundle.geometry_index["assets"]["FACE1"]["path"] == "geometry/FACE1.brep"
    assert bundle.geometry_index["assets"]["FACE1"]["sha256"]
    assert bundle.geometry_assets["FACE1"] == tmp_path / f"{source_id}.brep"
