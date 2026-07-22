from uuid import uuid4

from app.measurement.fact_builder import build_measurement_facts
from app.measurement.schemas import EntityFact


def entity(entity_type, geometry_type=None, geometry=None, center=None, bbox=None, area=None, parent=None):
    return EntityFact(
        id=uuid4(),
        revision_id=uuid4(),
        parent_entity_id=parent,
        entity_type=entity_type,
        geometry_type=geometry_type,
        geometry=geometry or {},
        center=center,
        bounding_box=bbox,
        area=area,
        length=None,
        source_ref=None,
    )


def test_builds_generic_measurements_without_domain_specific_names():
    solid_id = uuid4()
    root = EntityFact(
        id=solid_id,
        revision_id=uuid4(),
        parent_entity_id=None,
        entity_type="solid",
        geometry_type=None,
        geometry={},
        center=[0, 0, 0],
        bounding_box={"min": [-5, -5, 0], "max": [5, 5, 20]},
        area=None,
        length=None,
        source_ref="Solid1",
    )
    cylinder = entity(
        "face",
        "cylinder",
        {"axis": [0, 0, 1], "center": [0, 0, 10], "radius": 3},
        center=[0, 0, 10],
        bbox={"min": [-3, -3, 0], "max": [3, 3, 20]},
        area=120,
        parent=solid_id,
    )
    circle = entity(
        "edge",
        "circle",
        {"axis": [0, 0, 1], "center": [4, 0, 10], "radius": 1},
        center=[4, 0, 10],
        bbox={"min": [3, -1, 10], "max": [5, 1, 10]},
        parent=solid_id,
    )
    cone = entity(
        "face",
        "cone",
        {"axis": [0, 0, 1], "center": [0, 0, 4], "semi_angle": 0.25},
        center=[0, 0, 4],
        bbox={"min": [-2, -2, 0], "max": [2, 2, 8]},
        area=25,
        parent=solid_id,
    )
    plane_a = entity("face", "plane", {"normal": [0, 0, 1], "position": [0, 0, 0]}, parent=solid_id)
    plane_b = entity("face", "plane", {"normal": [0, 0, 1], "position": [0, 0, 20]}, parent=solid_id)

    facts = build_measurement_facts([root, cylinder, circle, cone, plane_a, plane_b])
    measurement_types = {measurement.measurement_type for measurement in facts.measurements}
    feature_types = {feature.feature_type for feature in facts.features}

    assert "main_axis_candidate" in feature_types
    assert "cylindrical_hole_candidate" in feature_types
    assert "bounding_box_x" in measurement_types
    assert "bounding_box_y" in measurement_types
    assert "bounding_box_z" in measurement_types
    assert "overall_length_along_main_axis" in measurement_types
    assert "maximum_radial_diameter" in measurement_types
    assert "cylinder_diameter" in measurement_types
    assert "circle_diameter" in measurement_types
    assert "parallel_plane_distance" in measurement_types
    assert "fillet_radius_candidate" in measurement_types
    assert "cone_angle_candidate" in measurement_types

    forbidden = {
        "flange_outer_diameter",
        "bolt_hole",
        "gear_module",
        "bearing_outer_diameter",
    }
    assert forbidden.isdisjoint(measurement_types)
    assert forbidden.isdisjoint(feature_types)


def test_detects_circular_pattern_with_generic_parameters():
    revision_id = uuid4()
    solid_id = uuid4()
    solid = EntityFact(
        id=solid_id,
        revision_id=revision_id,
        parent_entity_id=None,
        entity_type="solid",
        geometry_type=None,
        geometry={},
        center=[0, 0, 0],
        bounding_box={"min": [-10, -10, -1], "max": [10, 10, 1]},
        area=None,
        length=None,
        source_ref="Solid1",
    )
    circles = [
        EntityFact(
            id=uuid4(),
            revision_id=revision_id,
            parent_entity_id=solid_id,
            entity_type="edge",
            geometry_type="circle",
            geometry={"axis": [0, 0, 1], "center": center, "radius": 1},
            center=center,
            bounding_box=None,
            area=None,
            length=None,
            source_ref=f"Edge{index + 1}",
        )
        for index, center in enumerate([[5, 0, 0], [0, 5, 0], [-5, 0, 0], [0, -5, 0]])
    ]

    facts = build_measurement_facts([solid, *circles])
    pattern = next(feature for feature in facts.features if feature.feature_type == "circular_pattern")

    assert pattern.parameters["count"] == 4
    assert pattern.parameters["member_diameter"] == 2
    assert pattern.parameters["pitch_circle_diameter"] == 10
    assert pattern.parameters["angular_spacing"] == 90
    assert len(pattern.parameters["member_feature_ids"]) == 4


def test_main_axis_uses_geometry_axis_and_bounding_box_fallback_without_assuming_z():
    revision_id = uuid4()
    solid_id = uuid4()
    solid = EntityFact(
        id=solid_id,
        revision_id=revision_id,
        parent_entity_id=None,
        entity_type="solid",
        geometry_type=None,
        geometry={},
        center=[0, 0, 0],
        bounding_box={"min": [0, 0, 0], "max": [30, 5, 5]},
        area=None,
        length=None,
        source_ref="Solid1",
    )
    cylinder = EntityFact(
        id=uuid4(),
        revision_id=revision_id,
        parent_entity_id=solid_id,
        entity_type="face",
        geometry_type="cylinder",
        geometry={"axis": [1, 0, 0], "center": [15, 0, 0], "radius": 2},
        center=[15, 0, 0],
        bounding_box=None,
        area=100,
        length=None,
        source_ref="Face1",
    )

    facts = build_measurement_facts([solid, cylinder])
    axis = next(feature for feature in facts.features if feature.feature_type == "main_axis_candidate")
    assert axis.axis == [1.0, 0.0, 0.0]

    fallback_facts = build_measurement_facts([solid])
    fallback_axis = next(feature for feature in fallback_facts.features if feature.feature_type == "main_axis_candidate")
    assert fallback_axis.axis == [1.0, 0.0, 0.0]
