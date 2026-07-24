from copy import deepcopy

from app.component_builds.component_spec import component_spec_template
from app.component_builds.fusion import FusionSources, fuse_component_spec


def blank_spec():
    return component_spec_template.blank_data()


def build_fields(**overrides):
    fields = {
        "component_id": "flange-001",
        "component_name": "XMS06-DN80",
        "component_type": "flange",
        "component_subtype": None,
        "family": "connection-fastening",
        "standard_number": "HG/T 20592-2009",
        "version": "1.0.0",
        "default_dn": None,
        "default_pn": None,
    }
    fields.update(overrides)
    return fields


def fact(
    key,
    value,
    *,
    fact_type="dimension",
    symbol=None,
    row_dn=None,
    unit="mm",
    operator="eq",
    confidence=0.85,
):
    return {
        "fact_key": key,
        "fact_type": fact_type,
        "symbol": symbol,
        "normalized_value": value,
        "unit": unit,
        "operator": operator,
        "confidence": confidence,
        "metadata": {"row_dn": row_dn} if row_dn is not None else {},
    }


def product_facts():
    return [
        fact(
            "product.component_code",
            "XMS05, XMS06",
            fact_type="product_info",
            unit=None,
            operator="categorical",
            confidence=0.9,
        ),
        fact(
            "product.component_type_raw",
            "带颈对焊",
            fact_type="product_info",
            unit=None,
            operator="categorical",
            confidence=0.9,
        ),
        fact(
            "product.facing_type",
            "突面 (RF)",
            fact_type="product_info",
            unit=None,
            operator="categorical",
            confidence=0.9,
        ),
        fact(
            "product.pressure_class",
            "PN16",
            fact_type="pressure_class",
            unit=None,
            operator="categorical",
            confidence=0.9,
        ),
        fact(
            "product.standard_number",
            "HG/T 20592-2009",
            fact_type="product_info",
            unit=None,
            operator="categorical",
            confidence=0.9,
        ),
    ]


def dimension_row(dn, **values):
    operators = {"S": "gte", "H1": "approx"}
    return [
        fact(
            f"dimension.DN{dn}.{symbol}",
            value,
            symbol=symbol,
            row_dn=dn,
            unit="mm",
            operator=operators.get(symbol, "eq"),
        )
        for symbol, value in values.items()
    ]


def xms06_sources(*, confirm_bore=True):
    measurements = [
        {
            "measurement_type": "cylinder_diameter",
            "normalized_value": {"value": 82.6 if confirm_bore else 81.0},
            "unit": "mm",
            "confidence": 0.85,
        }
    ]
    features = [
        {
            "feature_type": "main_axis_candidate",
            "axis": [0.0, 1.0, 0.0],
            "center": [0.0, -25.0, 0.0],
            "confidence": 0.95,
            "parameters": {"axis_origin": [0.0, -25.0, 0.0]},
        },
        {
            "feature_type": "circular_pattern",
            "axis": [0.0, 1.0, 0.0],
            "center": [0.0, -40.0, 0.0],
            "confidence": 0.85,
            "parameters": {
                "count": 8,
                "member_diameter": 18.0,
                "pitch_circle_diameter": 160.0,
                "center": [0.0, -40.0, 0.0],
                "axis": [0.0, 1.0, 0.0],
                "start_angle": 0.0,
            },
        },
    ]
    return FusionSources(
        drawing_facts=product_facts()
        + dimension_row(15, D=95.0, K=65.0, n=4.0, L=14.0)
        + dimension_row(
            80,
            A1=89.0,
            D=200.0,
            K=160.0,
            L=18.0,
            n=8.0,
            C=20.0,
            N=105.0,
            S=3.2,
            H1=10.0,
            R=6.0,
            H=50.0,
            d=138.0,
            f1=2.0,
        ),
        measurements=measurements,
        features=features,
        revision={
            "source_file_name": "XMS06-DN80.stp",
            "source_sha256": "abc123",
            "parser_name": "FreeCAD",
            "unit": "mm",
            "object_count": 1,
            "solid_count": 1,
            "bounding_box": {
                "min": [-100.0, -50.0, -100.0],
                "max": [100.0, 0.0, 100.0],
            },
        },
    )


def parameter(spec, name):
    return next(item for item in spec["parameters"] if item["name"] == name)


def test_fusion_populates_identity_without_overwriting_manual_values():
    current = blank_spec()
    current["identity"]["name"] = "人工名称"

    result = fuse_component_spec(
        build=build_fields(),
        current=current,
        sources=FusionSources(drawing_facts=product_facts(), measurements=[], features=[]),
    )

    assert result.data["identity"]["id"] == "flange-001"
    assert result.data["identity"]["name"] == "人工名称"
    assert result.data["identity"]["subtype"] == "weld_neck"
    assert result.data["identity"]["standard"]["edition"] == "2009"
    assert any(item["path"] == "identity.name" and item["decision"] == "preserved" for item in result.fields)


def test_fusion_does_not_choose_a_dimension_row_when_target_dn_is_unknown():
    result = fuse_component_spec(
        build=build_fields(component_name="未命名法兰"),
        current=blank_spec(),
        sources=FusionSources(
            drawing_facts=dimension_row(15, D=95.0) + dimension_row(80, D=200.0),
            measurements=[],
            features=[],
        ),
    )

    assert all(item.get("name") != "flange_outer_diameter" for item in result.data["parameters"])
    assert "target_dn_unresolved" in result.warnings


def test_flange_fusion_maps_only_dn80_and_builds_matching_preset():
    result = fuse_component_spec(
        build=build_fields(),
        current=blank_spec(),
        sources=xms06_sources(),
    )

    assert parameter(result.data, "DN")["default"] == 80
    assert parameter(result.data, "PN")["default"] == 16
    assert parameter(result.data, "flange_outer_diameter")["default"] == 200.0
    assert parameter(result.data, "bolt_circle_diameter")["default"] == 160.0
    assert parameter(result.data, "bolt_hole_count")["default"] == 8
    assert parameter(result.data, "bolt_hole_count")["unit"] is None
    assert parameter(result.data, "bore_diameter")["default"] == 82.6
    assert result.data["presets"][0]["name"] == "DN80-PN16"
    assert result.data["presets"][0]["params"]["raised_face_diameter"] == 138.0
    assert result.data["validation"]["topology"]["expected_body_count"] == 1
    assert result.data["validation"]["topology"]["solid_required"] is True
    assert result.data["artifacts"]["reference_step"]["file"] == "XMS06-DN80.stp"
    assert result.data["artifacts"]["reference_step"]["sha256"] == "abc123"
    assert result.data["coordinate_system"]["origin"] == [0.0, -50.0, 0.0]
    assert result.data["coordinate_system"]["x_axis"] == [0.0, 0.0, -1.0]
    assert result.data["coordinate_system"]["y_axis"] == [-1.0, 0.0, 0.0]
    assert result.data["coordinate_system"]["z_axis"] == [0.0, 1.0, 0.0]
    assert result.data["coordinate_system"]["origin_definition"].startswith("法兰密封端面中心")
    assert result.data["geometry"]["representation"] == "parametric_recipe"
    assert result.data["geometry"]["modeling_kernel"] == "OpenCascade"
    assert result.data["geometry"]["generator"] == {
        "mode": "dsl_or_script",
        "preferred_engine": "CadQuery",
        "engine_version": "2.x",
        "script_file": "flange-weld-neck.py",
        "entrypoint": "build_component",
        "script_required_for_release": True,
    }
    assert [step["operation"] for step in result.data["geometry"]["construction"]] == [
        "revolve_profile",
        "polar_pattern_cut",
        "fillet",
    ]
    assert result.data["geometry"]["construction"][1]["count"] == "${bolt_hole_count}"
    assert result.data["geometry"]["output"]["filename_template"] == "${component_id}-${preset_name}.step"
    assert result.data["validation"]["geometry"]["bounding_box_expression"] == {
        "x_size": "flange_outer_diameter",
        "y_size": "flange_outer_diameter",
        "z_size": "overall_height",
    }
    assert result.data["validation"]["review"]["release_blocked_when_pending"] is True
    review_paths = {item["path"] for item in result.fields if item["needs_review"]}
    assert "parameters.wall_thickness.default" in review_paths
    assert "parameters.hub_height.default" in review_paths
    assert "coordinate_system.origin_definition" in review_paths


def test_bore_diameter_requires_matching_step_measurement():
    result = fuse_component_spec(
        build=build_fields(),
        current=blank_spec(),
        sources=xms06_sources(confirm_bore=False),
    )

    assert all(item.get("name") != "bore_diameter" for item in result.data["parameters"])
    assert "bore_diameter_unconfirmed" in result.warnings


def test_overwrite_mode_replaces_owned_fields_but_default_mode_preserves_them():
    initial = fuse_component_spec(
        build=build_fields(),
        current=blank_spec(),
        sources=xms06_sources(),
    ).data
    manual = deepcopy(initial)
    parameter(manual, "flange_outer_diameter")["default"] = 999.0
    parameter(manual, "bolt_hole_count")["unit"] = "mm"
    manual["identity"]["description"] = "人工说明"

    preserved = fuse_component_spec(
        build=build_fields(),
        current=manual,
        sources=xms06_sources(),
    )
    overwritten = fuse_component_spec(
        build=build_fields(),
        current=manual,
        sources=xms06_sources(),
        overwrite=True,
    )

    assert parameter(preserved.data, "flange_outer_diameter")["default"] == 999.0
    assert parameter(overwritten.data, "flange_outer_diameter")["default"] == 200.0
    assert parameter(overwritten.data, "bolt_hole_count")["unit"] is None
    assert overwritten.data["identity"]["description"] == "人工说明"
