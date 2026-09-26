"""New CAA channels use the existing database-only property projection."""
from types import SimpleNamespace
from uuid import uuid4

from app.component_builds.native_property_store import (
    build_database_properties,
    native_parameter_values,
    native_property_rows,
)


def test_typed_composite_values_and_failures_survive_existing_database_projection():
    facts = [
        {"subject_id": "object_1", "key": "composite_cured_thickness", "raw_value": "0.00033",
         "raw_unit": "m", "display_value": "0.33mm", "value_type": "number", "read_status": "available"},
        {"subject_id": "object_1", "key": "native_attribute:NonStructural", "raw_value": "false",
         "display_value": "false", "value_type": "boolean", "read_status": "available"},
        {"subject_id": "object_1", "key": "catia_user_comment", "raw_value": "",
         "display_value": "", "value_type": "string", "read_status": "available"},
        {"subject_id": "object_1", "key": "composite_area_m2", "raw_value": "",
         "display_value": "", "value_type": "number", "read_status": "unavailable"},
    ]
    rows = native_property_rows(uuid4(), facts)
    response = build_database_properties("occurrence_1", {"object_id": "object_1"},
                                         [SimpleNamespace(**row) for row in rows])
    fields = {f["key"]: f for tab in response["tabs"] for group in tab["groups"] for f in group["fields"]}
    assert response["property_count"] == 4
    assert fields["composite_cured_thickness"]["raw_value"] == "0.00033"
    assert fields["composite_cured_thickness"]["raw_unit"] == "m"
    assert fields["composite_cured_thickness"]["display_value"] == "0.33mm"
    assert fields["native_attribute:NonStructural"]["raw_value"] == "false"
    assert fields["catia_user_comment"]["read_status"] == "available"
    assert fields["catia_user_comment"]["raw_value"] == ""
    assert fields["composite_area_m2"]["read_status"] == "unavailable"


def test_tree_parameter_labels_keep_display_units_and_exclude_unsupported_object_values():
    facts = [
        {"subject_id": "number", "key": "catia_parameter_value_text", "raw_value": "0.00033",
         "raw_display_text": "0.33mm", "read_status": "available"},
        {"subject_id": "zero", "key": "catia_parameter_value_text", "raw_value": "0",
         "raw_display_text": "0deg", "read_status": "available"},
        {"subject_id": "curve", "key": "catia_parameter_value_status", "raw_value": "",
         "raw_display_text": "Curve", "read_status": "unsupported_type"},
    ]
    rows = [SimpleNamespace(**row) for row in native_property_rows(uuid4(), facts)]
    assert native_parameter_values(rows) == {"number": "0.33mm", "zero": "0deg"}
