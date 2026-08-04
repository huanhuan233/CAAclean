import json

from app.component_builds.geometry_compare import compare_feature_center_bundles


def _write_bundle(root, bbox, solids):
    root.mkdir()
    (root / "lightweight").mkdir()
    (root / "lightweight" / "model.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    (root / "parts.jsonl").write_text(json.dumps({"bounding_box": bbox}) + "\n", encoding="utf-8")
    records = [
        {
            "entity_type": "solid",
            "volume": volume,
            "bounding_box": solid_bbox,
        }
        for volume, solid_bbox in solids
    ]
    (root / "topology_entities.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_compare_accepts_duplicate_import_objects_and_small_step_tolerance(tmp_path):
    bbox_a = {"min": [-206.95, -230.0, -32.74], "max": [206.95, 280.0, 35.0]}
    bbox_b = {"min": [-206.95001, -230.0, -32.74], "max": [206.95001, 280.00018, 35.0]}
    solid_a = ({"min": [-200, -230, -30], "max": [200, 266, 0.75]})
    solid_b = ({"min": [-206, -230, -2], "max": [206, 280, 35]})
    _write_bundle(tmp_path / "step", bbox_a, [(270253.06, solid_a), (379067.48, solid_b)] * 2)
    _write_bundle(tmp_path / "catpart", bbox_b, [(270253.07, solid_a)] * 3 + [(379067.40, solid_b)] * 3)

    result = compare_feature_center_bundles(tmp_path / "step", tmp_path / "catpart")

    assert result["status"] == "match"
    assert result["step"]["unique_solid_count"] == 2
    assert result["catpart"]["unique_solid_count"] == 2
    assert result["tolerance_mm"] >= 0.01


def test_compare_rejects_empty_or_severely_different_geometry(tmp_path):
    _write_bundle(tmp_path / "step", {"min": [0, 0, 0], "max": [10, 10, 10]}, [(1000, {"min": [0, 0, 0], "max": [10, 10, 10]})])
    _write_bundle(tmp_path / "catpart", {"min": [0, 0, 0], "max": [100, 10, 10]}, [(10000, {"min": [0, 0, 0], "max": [100, 10, 10]})])

    result = compare_feature_center_bundles(tmp_path / "step", tmp_path / "catpart")

    assert result["status"] == "mismatch"
    assert "bounding_box_dimensions" in result["differences"]
