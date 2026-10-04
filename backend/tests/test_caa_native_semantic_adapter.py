"""The bundle seam must supply one native semantic fact per definition."""

import json

import pytest

from app.component_builds.caa_new_bundle import CaaNewBundleError, CaaNewBundleReader


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_new_capture_uses_typed_native_projection_once(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    write_jsonl(tmp_path / "object_entities.jsonl", [{"object_id": "object_1", "document_id": "doc_1", "update_status": "not_up_to_date"}])
    write_jsonl(tmp_path / "tree_occurrences.jsonl", [{"occurrence_id": "occurrence_1", "object_id": "object_1", "document_id": "doc_1", "product_occurrence_id": ""}])
    write_jsonl(tmp_path / "semantic_facets.jsonl", [{"facet_id": "semantic_facet_1", "subject_id": "object_1", "decoder_id": "NativeHoleDecoder"}])
    write_jsonl(tmp_path / "native_features.jsonl", [{"native_feature_id": "semantic_facet_1", "feature_id": "object_1", "decoder_id": "NativeHoleDecoder", "decode_level": "typed", "decode_status": "success", "native_hole": {"diameter_mm": 0, "thread": {"enabled": False, "description": None}}}])

    features = list(CaaNewBundleReader(tmp_path).iter_canonical_native_features())

    assert len(features) == 1
    assert features[0]["feature_id"] == "object_1"
    assert features[0]["document_id"] == "doc_1"
    assert features[0]["occurrence_ids"] == ["occurrence_1"]
    assert features[0]["update_status"] == "not_up_to_date"
    assert features[0]["native_hole"]["diameter_mm"] == 0
    assert features[0]["native_hole"]["thread"] == {"enabled": False, "description": None}


def test_legacy_capture_keeps_its_typed_payload(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"schema_version": "cad_parse_mvp_v11"}), encoding="utf-8")
    write_jsonl(tmp_path / "native_features.jsonl", [{"native_feature_id": "F1", "source_object_id": "F1", "decoder": "NativeHoleDecoder", "decoder_status": "success", "parameters": {"diameter_mm": 10}, "native_hole": {"diameter_mm": 10}}])

    features = list(CaaNewBundleReader(tmp_path).iter_canonical_native_features())

    assert len(features) == 1
    assert features[0]["feature_id"] == "F1"
    assert features[0]["decoder_id"] == "NativeHoleDecoder"
    assert features[0]["native_hole"]["diameter_mm"] == 10


def test_new_capture_missing_or_damaged_required_projection_is_not_empty(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    reader = CaaNewBundleReader(tmp_path)
    with pytest.raises(CaaNewBundleError, match="native_features.jsonl"):
        list(reader.iter_canonical_native_features())
    (tmp_path / "native_features.jsonl").write_text("{bad json}\n", encoding="utf-8")
    with pytest.raises(CaaNewBundleError, match="native_features.jsonl"):
        list(reader.iter_canonical_native_features())
    (tmp_path / "native_features.jsonl").write_text("", encoding="utf-8")
    assert list(reader.iter_canonical_native_features()) == []


def test_unknown_schema_fails_before_using_legacy_file(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"schema_version": "future_v999"}), encoding="utf-8")
    write_jsonl(tmp_path / "native_features.jsonl", [{"feature_id": "F1"}])
    with pytest.raises(CaaNewBundleError, match="unsupported"):
        CaaNewBundleReader(tmp_path)


def test_topology_kind_is_canonical_without_losing_raw_type(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    write_jsonl(tmp_path / "topology_entities.jsonl", [
        {"topology_id": "T1", "topology_kind": "face"},
        {"topology_id": "T2", "topology_kind": "unexpected_cell"},
    ])
    write_jsonl(tmp_path / "native_topology_cells.jsonl", [{"cell_id": "T1", "topology_kind": "face"}])
    reader = CaaNewBundleReader(tmp_path)

    assert [row["kind"] for row in reader.iter_topology_entities()] == ["face", "unknown"]
    assert [row["raw_topology_kind"] for row in reader.iter_topology_entities()] == ["face", "unexpected_cell"]
    assert list(reader.iter_topology_cells())[0]["kind"] == "face"


def test_summary_counts_definitions_once_and_separates_decode_levels(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    write_jsonl(tmp_path / "native_features.jsonl", [
        {"feature_id": "O1", "decoder_id": "NativeHoleDecoder", "decode_level": "typed", "decode_status": "success", "native_hole": {}},
        {"feature_id": "O2", "decoder_id": "", "decode_level": "type_only", "decode_status": "unsupported"},
    ])
    reader = CaaNewBundleReader(tmp_path)

    assert reader.semantic_summary() == {
        "definition_count": 2, "typed_count": 1, "type_only_count": 1,
        "generic_count": 0, "failed_count": 0, "unavailable_count": 0,
        "typed_by_decoder": {"NativeHoleDecoder": 1},
    }


def test_r21_fillet_chamfer_and_sketch_payloads_keep_definition_identity(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    objects = ["fillet_1", "chamfer_1", "sketch_1"]
    write_jsonl(tmp_path / "object_entities.jsonl", [
        {"object_id": name, "document_id": "part_1", "update_status": "up_to_date"} for name in objects
    ])
    write_jsonl(tmp_path / "tree_occurrences.jsonl", [
        {"occurrence_id": "occ_" + name, "object_id": name, "document_id": "part_1"} for name in objects
    ])
    write_jsonl(tmp_path / "semantic_facets.jsonl", [
        {"facet_id": "facet_" + name, "subject_id": name, "decoder_id": "Native" + name.split('_')[0].title() + "Decoder"}
        for name in objects
    ])
    write_jsonl(tmp_path / "native_features.jsonl", [
        {"native_feature_id": "facet_fillet_1", "feature_id": "fillet_1", "decoder_id": "NativeFilletDecoder",
         "decode_level": "typed", "decode_status": "success", "native_fillet": {"radius_mm": 3.0, "field_status": {"radius_mm": "success"}}},
        {"native_feature_id": "facet_chamfer_1", "feature_id": "chamfer_1", "decoder_id": "NativeChamferDecoder",
         "decode_level": "typed", "decode_status": "success", "native_chamfer": {"mode": "two_lengths", "d1_mm": 2.0, "d2_mm": 4.0}},
        {"native_feature_id": "facet_sketch_1", "feature_id": "sketch_1", "decoder_id": "NativeSketchDecoder",
         "decode_level": "typed", "decode_status": "success", "native_sketch": {"axis": {"origin_mm": [0, 0, 0]}, "elements": [{"element_id": "e1", "kind": "circle"}]}},
    ])
    features = list(CaaNewBundleReader(tmp_path).iter_canonical_native_features())
    assert len(features) == 3
    assert [feature["feature_id"] for feature in features] == objects
    assert features[0]["native_fillet"]["radius_mm"] == 3.0
    assert features[1]["native_chamfer"]["d2_mm"] == 4.0
    assert features[2]["native_sketch"]["elements"][0]["kind"] == "circle"
    assert CaaNewBundleReader(tmp_path).semantic_summary()["typed_count"] == 3
