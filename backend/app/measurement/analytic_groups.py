from __future__ import annotations

import math

from app.measurement.schemas import EntityFact, MeasurementFact


def build_analytic_measurements(entities: list[EntityFact]) -> list[MeasurementFact]:
    measurements: list[MeasurementFact] = []
    for entity in entities:
        radius = entity.geometry.get("radius")
        if radius is None:
            continue
        diameter = round(float(radius) * 2.0, 9)
        if entity.geometry_type == "cylinder":
            measurements.append(_measurement(entity, "cylinder_diameter", diameter, "analytic_surface_radius"))
            measurements.append(_measurement(entity, "fillet_radius_candidate", float(radius), "analytic_surface_radius"))
        if entity.geometry_type == "circle":
            measurements.append(_measurement(entity, "circle_diameter", diameter, "analytic_curve_radius"))
            measurements.append(_measurement(entity, "fillet_radius_candidate", float(radius), "analytic_curve_radius"))
    for entity in entities:
        if entity.geometry_type == "cone" and entity.geometry.get("semi_angle") is not None:
            angle = round(float(entity.geometry["semi_angle"]) * 2.0 * 180.0 / math.pi, 9)
            measurements.append(_measurement(entity, "cone_angle_candidate", angle, "analytic_cone_angle", unit="deg"))
    return measurements


def _measurement(entity: EntityFact, measurement_type: str, value: float, method: str, unit: str = "mm") -> MeasurementFact:
    normalized = round(float(value), 9)
    return MeasurementFact(
        revision_id=entity.revision_id,
        scope_entity_id=entity.parent_entity_id or entity.id,
        feature_id=None,
        measurement_type=measurement_type,
        raw_value={"value": normalized},
        normalized_value={"value": normalized},
        unit=unit,
        source_entity_ids=[entity.id],
        method=method,
        confidence=0.85,
    )
