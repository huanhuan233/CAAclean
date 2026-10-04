from __future__ import annotations

from app.assembly.connection_semantics import build_connection_semantics
import json

from app.component_builds.caa_new_bundle import CaaNewBundleReader


def _fact(subject: str, key: str, value: str) -> dict:
    return {"subject_id": subject, "key": key, "raw_value": value, "read_status": "available",
            "source_api": "verified_fixture"}


def test_same_native_set_definition_keeps_two_r_instances_separate_and_counts_point_numbers():
    objects = [{"object_id": item} for item in ("set", "fasteners", "point", "parameter")]
    products = [{"occurrence_id": "R1", "part_number": "R_ABC"},
                {"occurrence_id": "R2", "part_number": "R_ABC"}]
    occurrences = []
    for instance in ("R1", "R2"):
        occurrences.extend([
            {"occurrence_id": f"{instance}-root", "object_id": "set", "document_id": "D1",
             "product_occurrence_id": instance, "parent_occurrence_id": instance},
            {"occurrence_id": f"{instance}-group", "object_id": "fasteners", "document_id": "D1",
             "product_occurrence_id": instance, "parent_occurrence_id": f"{instance}-root"},
            {"occurrence_id": f"{instance}-point", "object_id": "point", "document_id": "D1",
             "product_occurrence_id": instance, "parent_occurrence_id": f"{instance}-group"},
        ])
    facts = [_fact("set", "native_alias", "连接定义"),
             _fact("set", "native_object_class", "geometrical_set"),
             _fact("fasteners", "native_alias", "A连接点"),
             _fact("fasteners", "native_object_class", "geometrical_set"),
             _fact("point", "native_alias", "M6+M8+M6+"),
             _fact("point", "native_object_class", "point_feature")]
    # No actual '紧固件' parent: this is path B and its missing chain remains visible.
    records = build_connection_semantics(objects, occurrences, facts, products)
    assert len(records) == 2
    assert records[0]["connection_id"] != records[1]["connection_id"]
    assert all(record["model_role"] == "R" and record["path"] == "B" for record in records)
    assert all(record["point_count"] == 1 and record["number_segment_count"] == 4 for record in records)
    point = records[0]["points"][0]
    assert point["customer_bucket"] == "fastener"
    assert point["number_diagnostics"] == ["empty_number_segment", "duplicate_number_segment"]
    assert point["coordinate_status"] == "unresolved_native_point_geometry"


def test_seal_and_bond_keep_exact_customer_keys_without_guessing_material_association():
    objects = [{"object_id": item} for item in ("seal", "bond", "p1", "p2")]
    products = [{"occurrence_id": "DM1", "part_number": "ABC"}]
    occurrences = [
        {"occurrence_id": "S", "object_id": "seal", "document_id": "D", "product_occurrence_id": "DM1",
         "parent_occurrence_id": "DM1"},
        {"occurrence_id": "B", "object_id": "bond", "document_id": "D", "product_occurrence_id": "DM1",
         "parent_occurrence_id": "DM1"},
        {"occurrence_id": "P1", "object_id": "p1", "document_id": "D", "product_occurrence_id": "DM1",
         "parent_occurrence_id": "S"},
        {"occurrence_id": "P2", "object_id": "p2", "document_id": "D", "product_occurrence_id": "DM1",
         "parent_occurrence_id": "B"},
    ]
    facts = [_fact("seal", "native_alias", "K_密封定义"),
             _fact("seal", "native_object_class", "geometrical_set"),
             _fact("bond", "native_alias", "M_胶接定义"),
             _fact("bond", "native_object_class", "geometrical_set"),
             _fact("p1", "catia_parameter_name", "F017_毛料尺寸"),
             _fact("p1", "catia_parameter_value_text", "20x30"),
             _fact("p2", "catia_parameter_name", "K001_面积"),
             _fact("p2", "catia_parameter_value_text", "100")]
    records = build_connection_semantics(objects, occurrences, facts, products)
    assert {record["kind"] for record in records} == {"seal", "bond"}
    seal = next(record for record in records if record["kind"] == "seal")
    bond = next(record for record in records if record["kind"] == "bond")
    assert seal["model_role"] == bond["model_role"] == "DM"
    assert seal["parameters_raw"][0]["name"] == "F017_毛料尺寸"
    assert bond["parameters_raw"][0]["name"] == "K001_面积"
    assert bond["material_association_status"] == "parent_reference_not_verified"
    assert bond["geometry_status"] == "native_region_geometry_unresolved"


def test_display_name_alone_is_not_a_connection_entry():
    records = build_connection_semantics([{"object_id": "set", "display_name": "连接定义"}],
                                         [{"occurrence_id": "O", "object_id": "set", "document_id": "D"}],
                                         [], [])
    assert records == []


def test_exact_customer_alias_with_catia_numeric_suffix_retains_raw_value():
    records = build_connection_semantics([{"object_id": "set"}],
        [{"occurrence_id": "O", "object_id": "set", "document_id": "D"}],
        [_fact("set", "native_alias", "K_密封定义.2"),
         _fact("set", "native_object_class", "geometrical_set")], [])
    assert records[0]["kind"] == "seal"
    assert records[0]["raw_alias"] == "K_密封定义.2"


def test_path_a_counts_only_points_under_fastener_set_and_keeps_local_precision():
    names = {"root": "连接定义", "fast": "紧固件", "group": "A1", "other": "A2",
             "point": "001+002", "outside": "003"}
    objects = [{"object_id": name} for name in names]
    parents = {"root": "PRODUCT", "fast": "root", "group": "fast", "other": "root",
               "point": "group", "outside": "other"}
    occurrences = [{"occurrence_id": name, "object_id": name, "document_id": "DOC",
                    "product_occurrence_id": "PRODUCT", "parent_occurrence_id": parent}
                   for name, parent in parents.items()]
    facts = [_fact(name, "native_alias", alias) for name, alias in names.items()]
    facts += [_fact(name, "native_object_class", "geometrical_set")
              for name in ("root", "fast", "group", "other")]
    facts += [_fact(name, "native_object_class", "point_feature") for name in ("point", "outside")]
    facts += [_fact("point", f"native_point_{axis}_m", value)
              for axis, value in zip("xyz", ("0.00123456789", "0", "-0.002"))]
    facts += [_fact("point", "native_point_reference_status", "absolute_part_axis")]
    record = build_connection_semantics(objects, occurrences, facts,
                                        [{"occurrence_id": "PRODUCT", "part_number": "R_1"}])[0]
    assert record["path"] == "A"
    assert record["point_count"] == 2
    assert record["fastener_point_count"] == 1
    point = next(item for item in record["points"] if item["point_object_id"] == "point")
    assert point["part_local_mm"] == [1.23456789, 0, -2]
    assert point["assembly_world_mm"] is None
    outside = next(item for item in record["points"] if item["point_object_id"] == "outside")
    assert outside["customer_bucket"] == "outside_fastener_set"
    assert "outside_fastener_parent" in outside["number_diagnostics"]


def test_coordinate_defined_point_uses_verified_absolute_product_transform_once():
    matrix = [1, 0, 0, 10, 0, 1, 0, -5, 0, 0, 1, 3, 0, 0, 0, 1]
    objects = [{"object_id": "set"}, {"object_id": "point"}]
    occurrences = [
        {"occurrence_id": "root", "object_id": "set", "document_id": "D",
         "product_occurrence_id": "R1", "parent_occurrence_id": "R1"},
        {"occurrence_id": "point", "object_id": "point", "document_id": "D",
         "product_occurrence_id": "R1", "parent_occurrence_id": "root"},
    ]
    facts = [_fact("set", "native_alias", "连接定义"),
             _fact("set", "native_object_class", "geometrical_set"),
             _fact("point", "native_object_class", "point_feature"),
             _fact("point", "native_point_reference_status", "absolute_part_axis")]
    facts += [_fact("point", f"native_point_{axis}_m", value)
              for axis, value in zip("xyz", ("0.001", "0.002", "0.003"))]
    product = {"occurrence_id": "R1", "part_number": "R_1", "transform_status": "resolved_absolute",
               "transform_4x4": matrix}
    point = build_connection_semantics(objects, occurrences, facts, [product])[0]["points"][0]
    assert point["assembly_world_mm"] == [11, -3, 6]
    assert point["coordinate_status"] == "assembly_world_verified"


def test_bundle_publishes_native_connection_projection_only_from_captured_alias_and_hierarchy(tmp_path):
    bundle = tmp_path / "capture"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    rows = {
        "object_entities.jsonl": [{"object_id": "SET"}, {"object_id": "POINT"}],
        "tree_occurrences.jsonl": [
            {"occurrence_id": "O1", "object_id": "SET", "document_id": "D1",
             "product_occurrence_id": "R1", "parent_occurrence_id": "R1"},
            {"occurrence_id": "O2", "object_id": "POINT", "document_id": "D1",
             "product_occurrence_id": "R1", "parent_occurrence_id": "O1"}],
        "property_facts.jsonl": [_fact("SET", "native_alias", "连接定义"),
                                 _fact("SET", "native_object_class", "geometrical_set"),
                                 _fact("POINT", "native_object_class", "point_feature")],
        "product_occurrences.jsonl": [{"occurrence_id": "R1", "part_number": "R_123"}],
    }
    for filename, records in rows.items():
        (bundle / filename).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
                                       encoding="utf-8")
    streams = CaaNewBundleReader(bundle).native_evidence_streams()
    connection = streams["connection_semantics"][0]
    assert connection["part_number"] == "R_123"
    assert connection["points"][0]["point_object_id"] == "POINT"
    assert streams["connection_semantics_status"][0]["connection_count"] == 1
