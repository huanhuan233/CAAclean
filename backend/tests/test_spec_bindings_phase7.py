from __future__ import annotations

from uuid import UUID, uuid4

from app.db.models import CadSpecField, CadSpecFieldEvidence
from app.spec.bindings import bind_spec_fields


TASK_ID = UUID("22222222-2222-2222-2222-222222222222")
REVISION_ID = UUID("33333333-3333-3333-3333-333333333333")


def drawing_fact(symbol: str, value, *, fact_id=None, operator: str = "eq", unit: str = "mm"):
    return {
        "id": fact_id or uuid4(),
        "fact_key": f"dimension.{symbol}",
        "fact_type": "dimension",
        "symbol": symbol,
        "label": symbol,
        "operator": operator,
        "raw_value": str(value),
        "normalized_value": value,
        "unit": unit,
        "confidence": 0.92,
        "source_region_id": uuid4(),
        "source_bbox_original": [1, 2, 3, 4],
        "source_bbox_precision": "row",
    }


def measurement(measurement_type: str, value, *, measurement_id=None, feature_id=None, confidence: float = 0.94):
    entity_id = uuid4()
    return {
        "id": measurement_id or uuid4(),
        "feature_id": feature_id,
        "measurement_type": measurement_type,
        "raw_value": {"value": value},
        "normalized_value": {"value": value},
        "unit": "mm",
        "source_entity_ids": [entity_id],
        "confidence": confidence,
    }


def test_phase7_models_define_separate_status_columns_and_evidence_links():
    assert CadSpecField.__tablename__ == "cad_spec_fields"
    assert CadSpecFieldEvidence.__tablename__ == "cad_spec_field_evidence"

    field_columns = CadSpecField.__table__.columns
    for column in [
        "drawing_value",
        "measured_value",
        "normalized_measured_value",
        "resolved_value",
        "unit",
        "drawing_fact_id",
        "measurement_id",
        "feature_id",
        "source_entity_ids",
        "mapping_status",
        "geometry_match_status",
        "conformance_status",
        "review_status",
        "drawing_value_confidence",
        "measurement_confidence",
        "mapping_confidence",
    ]:
        assert column in field_columns


def test_profile_symbol_and_measurement_type_map_to_spec_field_without_overwriting_drawing_value():
    drawing_fact_id = uuid4()
    measurement_id = uuid4()
    feature_id = uuid4()
    bindings = bind_spec_fields(
        task_id=TASK_ID,
        revision_id=REVISION_ID,
        drawing_facts=[drawing_fact("D", 200, fact_id=drawing_fact_id)],
        measurements=[measurement("maximum_radial_diameter", 199.96, measurement_id=measurement_id, feature_id=feature_id)],
        component_type="flange",
        subtype="weld_neck",
        profile_id="flange-weld-neck-hgt20592",
    )

    field = bindings[0]
    assert field.field_name == "flange_outer_diameter"
    assert field.drawing_value == 200
    assert field.measured_value == 199.96
    assert field.normalized_measured_value == 199.96
    assert field.resolved_value == 200
    assert field.drawing_fact_id == drawing_fact_id
    assert field.measurement_id == measurement_id
    assert field.feature_id == feature_id
    assert field.mapping_status == "matched"
    assert field.geometry_match_status == "within_match_tolerance"
    assert field.conformance_status == "unknown"
    assert field.review_status == "pending"
    assert field.drawing_value_confidence == 0.92
    assert field.measurement_confidence == 0.94
    assert field.mapping_confidence > 0.8
    assert field.reason


def test_geometry_outside_tolerance_does_not_change_resolved_drawing_value_or_claim_fail():
    bindings = bind_spec_fields(
        task_id=TASK_ID,
        revision_id=REVISION_ID,
        drawing_facts=[drawing_fact("H", 50)],
        measurements=[measurement("overall_length_along_main_axis", 52)],
        component_type="flange",
        subtype="weld_neck",
        profile_id="flange-weld-neck-hgt20592",
    )

    field = bindings[0]
    assert field.field_name == "overall_height"
    assert field.drawing_value == 50
    assert field.measured_value == 52
    assert field.resolved_value == 50
    assert field.geometry_match_status == "outside_match_tolerance"
    assert field.conformance_status == "unknown"


def test_numeric_proximity_alone_cannot_bind_a_measurement():
    bindings = bind_spec_fields(
        task_id=TASK_ID,
        revision_id=REVISION_ID,
        drawing_facts=[drawing_fact("D", 200)],
        measurements=[measurement("overall_length_along_main_axis", 200)],
        component_type="flange",
        subtype="weld_neck",
        profile_id="flange-weld-neck-hgt20592",
    )

    field = bindings[0]
    assert field.field_name == "flange_outer_diameter"
    assert field.measurement_id is None
    assert field.measured_value is None
    assert field.geometry_match_status == "not_measurable"
    assert field.reason == "profile_symbol_matched_no_measurement_type_match"


def test_comparison_operators_are_preserved_and_evaluated_for_geometry_match_only():
    bindings = bind_spec_fields(
        task_id=TASK_ID,
        revision_id=REVISION_ID,
        drawing_facts=[drawing_fact("S", 3.2, operator="gte")],
        measurements=[measurement("wall_thickness_candidate", 3.4)],
        component_type="flange",
        subtype="weld_neck",
        profile_id="flange-weld-neck-hgt20592",
    )

    field = bindings[0]
    assert field.field_name == "minimum_wall_thickness_candidate"
    assert field.resolved_value == 3.2
    assert field.geometry_match_status == "within_match_tolerance"
    assert field.conformance_status == "unknown"
    assert field.metadata["operator"] == "gte"


def test_ambiguous_and_unmatched_mapping_statuses_are_distinct():
    ambiguous = bind_spec_fields(
        task_id=TASK_ID,
        revision_id=REVISION_ID,
        drawing_facts=[drawing_fact("D", 200), drawing_fact("D", 201)],
        measurements=[],
        component_type="flange",
        subtype="weld_neck",
        profile_id="flange-weld-neck-hgt20592",
    )
    unmatched = bind_spec_fields(
        task_id=TASK_ID,
        revision_id=REVISION_ID,
        drawing_facts=[drawing_fact("ZZ", 12)],
        measurements=[],
        component_type="flange",
        subtype="weld_neck",
        profile_id="flange-weld-neck-hgt20592",
    )

    assert ambiguous[0].mapping_status == "ambiguous"
    assert ambiguous[0].field_name == "flange_outer_diameter"
    assert unmatched[0].mapping_status == "unmatched"
    assert unmatched[0].field_name == "drawing_parameter_ZZ"
    assert unmatched[0].review_status == "needs_review"
