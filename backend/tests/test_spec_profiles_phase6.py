from __future__ import annotations

import json
from pathlib import Path

from app.spec.mapper import build_component_spec
from app.spec.registry import ProfileRegistry
from app.spec.templates import sanitize_template_structure


def drawing_fact(symbol: str, value, *, operator: str = "eq"):
    return {
        "fact_key": f"dimension.{symbol}",
        "fact_type": "dimension",
        "symbol": symbol,
        "raw_value": str(value),
        "normalized_value": value,
        "unit": "mm",
        "operator": operator,
        "source_region_id": "11111111-1111-1111-1111-111111111111",
        "source_bbox_original": [1, 2, 3, 4],
        "source_bbox_precision": "row",
        "confidence": 0.9,
    }


def test_component_schema_file_defines_required_structures_and_enums():
    schema_path = Path(__file__).resolve().parents[1] / "app/spec/component-spec.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert "parameters" in schema["required"]
    assert schema["properties"]["parameters"]["type"] == "array"
    assert "needs_review" in schema["properties"]["parameters"]["items"]["required"]
    assert "skeleton" in schema["properties"]["template_mode"]["enum"]
    assert "field-template" in schema["properties"]["template_mode"]["enum"]


def test_registry_loads_flange_profile_and_maps_only_profile_fields():
    registry = ProfileRegistry.default()
    profile = registry.get("flange-weld-neck-hgt20592")

    assert profile.profile_id == "flange-weld-neck-hgt20592"
    assert profile.field_mappings["D"].target_field == "flange_outer_diameter"
    assert profile.field_mappings["K"].target_field == "bolt_circle_diameter"
    assert profile.field_mappings["n"].target_field == "bolt_hole_count"
    assert profile.field_mappings["L"].target_field == "bolt_hole_diameter"
    assert profile.field_mappings["C"].target_field == "flange_thickness"
    assert profile.field_mappings["H"].target_field == "overall_height"
    assert profile.field_mappings["R"].target_field == "root_fillet_radius"
    assert profile.field_mappings["f1"].target_field == "raised_face_height"
    assert profile.field_mappings["A1"].target_field == "pipe_outer_diameter"
    assert profile.field_mappings["N"].target_field == "hub_small_end_diameter"
    assert "H1" not in profile.field_mappings
    assert profile.ambiguity_candidates["H1"][0]["needs_review"] is True
    assert profile.field_mappings["d"].target_field == "flange_bore_diameter"
    assert profile.field_mappings["d"].needs_review is True


def test_flange_profile_builds_component_parameters_and_keeps_h1_ambiguous():
    facts = [
        drawing_fact("D", 200),
        drawing_fact("K", 160),
        drawing_fact("n", 8),
        drawing_fact("L", 18),
        drawing_fact("C", 20),
        drawing_fact("H", 50),
        drawing_fact("R", 6),
        drawing_fact("f1", 2),
        drawing_fact("A1", 89),
        drawing_fact("N", 105),
        drawing_fact("H1", 10, operator="approx"),
    ]

    spec = build_component_spec(facts, component_type="flange", subtype="weld_neck", profile_id="flange-weld-neck-hgt20592")
    params = {item["name"]: item for item in spec["parameters"]}

    assert params["flange_outer_diameter"]["normalized_value"] == 200
    assert params["bolt_circle_diameter"]["normalized_value"] == 160
    assert params["bolt_hole_count"]["normalized_value"] == 8
    assert params["bolt_hole_diameter"]["normalized_value"] == 18
    assert params["flange_thickness"]["normalized_value"] == 20
    assert params["overall_height"]["normalized_value"] == 50
    assert params["root_fillet_radius"]["normalized_value"] == 6
    assert params["raised_face_height"]["normalized_value"] == 2
    assert params["pipe_outer_diameter"]["normalized_value"] == 89
    assert params["hub_small_end_diameter"]["normalized_value"] == 105
    assert "H1" not in params
    assert params["drawing_parameter_H1"]["needs_review"] is True
    assert params["drawing_parameter_H1"]["metadata"]["ambiguity_candidates"]


def test_generic_profile_never_emits_flange_fields():
    spec = build_component_spec(
        [drawing_fact("D", 200), drawing_fact("K", 160)],
        component_type="unknown",
        subtype=None,
        profile_id="generic",
    )

    params = {item["name"]: item for item in spec["parameters"]}
    assert "flange_outer_diameter" not in params
    assert "bolt_circle_diameter" not in params
    assert params["drawing_parameter_D"]["normalized_value"] == 200
    assert params["drawing_parameter_D"]["needs_review"] is True
    assert params["drawing_parameter_K"]["needs_review"] is True


def test_field_template_fills_by_parameter_name_not_index():
    template = {
        "parameters": [
            {"name": "bolt_circle_diameter", "value": 999},
            {"name": "flange_outer_diameter", "value": 999},
        ]
    }

    spec = build_component_spec(
        [drawing_fact("D", 200), drawing_fact("K", 160)],
        component_type="flange",
        subtype="weld_neck",
        profile_id="flange-weld-neck-hgt20592",
        template=template,
        template_mode="field-template",
    )
    params = spec["parameters"]

    assert [item["name"] for item in params] == ["bolt_circle_diameter", "flange_outer_diameter"]
    assert params[0]["normalized_value"] == 160
    assert params[1]["normalized_value"] == 200


def test_structure_only_template_strips_unverified_example_values():
    template = {
        "standard": "GB/T 9124.1-2019",
        "designation": "DN100-PN16",
        "author": "张三",
        "parameters": [
            {"name": "flange_outer_diameter", "value": 220.0},
            {"name": "bolt_circle_diameter", "normalized_value": 180.0},
        ],
    }

    sanitized = sanitize_template_structure(template, mode="structure_only")
    text = json.dumps(sanitized, ensure_ascii=False)

    assert "GB/T 9124.1-2019" not in text
    assert "DN100-PN16" not in text
    assert "张三" not in text
    assert "220.0" not in text
    assert sanitized["parameters"] == [{"name": "flange_outer_diameter"}, {"name": "bolt_circle_diameter"}]
