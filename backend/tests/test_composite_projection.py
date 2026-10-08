import json

from app.component_builds.composite_projection import build_composite_structure


def _object(object_id: str, kind: str, name: str = "Ply.1") -> dict:
    return {"object_id": object_id, "document_id": "doc_1", "startup_type": kind,
            "display_name": name, "update_status": "up_to_date"}


def _fact(subject: str, key: str, value: str, unit: str = "") -> dict:
    return {"subject_id": subject, "key": key, "raw_value": value, "raw_unit": unit,
            "read_status": "available", "source_api": "R21", "raw_display_text": value}


def test_native_order_and_physical_ply_identity_are_preserved():
    objects = [_object("s", "CATCompStacking", "Stacking"),
               _object("g", "CATCompPliesGroup", "Group"),
               _object("q", "CATCompSequence", "Sequence"),
               _object("p1", "CATCompPly"), _object("p2", "CATCompPly")]
    occurrences = [{"occurrence_id": "o1", "object_id": "p1", "parent_occurrence_id": "oq",
                    "tree_path": "/Stacking/Group/Sequence/Ply.1"},
                   {"occurrence_id": "o2", "object_id": "p1", "parent_occurrence_id": "oq",
                    "tree_path": "/other/Ply.1"},
                   {"occurrence_id": "o3", "object_id": "p2", "parent_occurrence_id": "oq",
                    "tree_path": "/Stacking/Group/Sequence/Ply.1"},
                   {"occurrence_id": "oq", "object_id": "q", "parent_occurrence_id": "og"},
                   {"occurrence_id": "og", "object_id": "g", "parent_occurrence_id": "os"},
                   {"occurrence_id": "os", "object_id": "s", "parent_occurrence_id": ""}]
    facts = [_fact("s", "composite_native_ordered_child_ids", '["g"]'),
             _fact("g", "composite_native_ordered_child_ids", '["q"]'),
             _fact("q", "composite_native_ordered_child_ids", '["p2","p1"]'),
             _fact("p1", "composite_orientation", "0", "rad"),
             _fact("p1", "composite_cured_thickness", "0.00033", "m"),
             _fact("p1", "composite_area_m2", "1", "m2")]
    rows = build_composite_structure(objects, occurrences, facts)
    assert len([row for row in rows if row["kind"] == "ply"]) == 2
    p1 = next(row for row in rows if row["object_id"] == "p1")
    assert p1["occurrence_ids"] == ["o1", "o2"]
    assert p1["parent_object_ids"] == ["q"]
    assert p1["fields"]["composite_orientation"]["normalized_value"] == 0
    assert p1["fields"]["composite_cured_thickness"]["normalized_value"] == 0.33
    assert p1["fields"]["composite_cured_thickness"]["normalized_unit"] == "mm"
    assert p1["fields"]["composite_area_m2"]["normalized_value"] == 1_000_000
    assert next(row for row in rows if row["object_id"] == "q")["ordered_child_object_ids"] == ["p2", "p1"]


def test_old_bundle_order_remains_unknown_and_failed_fields_are_not_inherited():
    rows = build_composite_structure(
        [_object("g", "CATCompPliesGroup"), _object("p", "CATCompPly")],
        [{"occurrence_id": "og", "object_id": "g"},
         {"occurrence_id": "op", "object_id": "p", "parent_occurrence_id": "og"}],
        [_fact("g", "composite_cured_thickness", "0.0002", "m"),
         {**_fact("p", "composite_cured_thickness", "", "m"), "read_status": "failed"}])
    group = next(row for row in rows if row["object_id"] == "g")
    ply = next(row for row in rows if row["object_id"] == "p")
    assert group["order_status"] == "unavailable"
    assert group["ordered_child_object_ids"] is None
    assert ply["fields"]["composite_cured_thickness"]["read_status"] == "failed"
    assert ply["fields"]["composite_cured_thickness"]["normalized_value"] is None


def test_cut_pieces_are_children_of_one_physical_ply_not_extra_plies():
    rows = build_composite_structure(
        [_object("ply", "CATCompPly"), _object("a", "CATCompCutPiece"),
         _object("b", "CATCompCutPiece")], [],
        [_fact("ply", "composite_cut_piece_object_ids", '["a","b"]')])
    ply = next(row for row in rows if row["object_id"] == "ply")
    assert ply["cut_piece_object_ids"] == ["a", "b"]
    assert len([row for row in rows if row["kind"] == "ply"]) == 1
    assert all("ply" in row["parent_object_ids"] for row in rows if row["kind"] == "cut_piece")


def test_unknown_units_and_unresolved_order_are_explicit():
    rows = build_composite_structure(
        [_object("sequence", "CATCompSequence")], [],
        [_fact("sequence", "composite_native_ordered_child_ids", '["missing",null]'),
         _fact("sequence", "composite_cured_thickness", "2", "in")])
    row = rows[0]
    assert row["order_status"] == "partial"
    assert row["ordered_child_object_ids"] == ["missing", None]
    assert "unresolved_native_order_member" in row["diagnostics"]
    assert row["fields"]["composite_cured_thickness"]["normalized_value"] is None


def test_native_surface_boundary_keeps_geometry_role_and_original_area_separate():
    payload = {"expected_unique_edges": 1, "visited_unique_edges": 1,
               "visited_edge_occurrences": 1, "faces": [{"face_index": 1, "loops": [
                   {"domain_index": 1, "location": "outer", "edges": [
                       {"edge_index": 1, "length_mm": 10, "curve_type": "circle"}]}]}]}
    rows = build_composite_structure([_object("p", "CATCompPly")], [], [
        _fact("p", "composite_surface_native_boundary_loops", json.dumps(payload)),
        _fact("p", "composite_area_m2", "0.25", "m2"),
    ])
    row = rows[0]
    assert row["boundary"]["geometry_role"] == "ply_surface"
    assert row["boundary"]["effective_boundary_length_mm"] == 10
    assert row["boundary"]["area_mm2"] is None
    assert row["fields"]["composite_area_m2"]["normalized_value"] == 250_000
    assert row["render_status"] == "unavailable_without_verified_ply_mesh"
