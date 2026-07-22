from __future__ import annotations

import math

from app.measurement.axis_detector import dot, normalize, projected_length
from app.measurement.schemas import EntityFact, MeasurementFact


def build_envelope_measurements(entities: list[EntityFact], axis_feature) -> list[MeasurementFact]:
    scope = next((entity for entity in entities if entity.entity_type == "solid" and entity.bounding_box), None)
    if scope is None:
        scope = next((entity for entity in entities if entity.bounding_box), None)
    if scope is None or scope.bounding_box is None:
        return []

    bbox = scope.bounding_box
    spans = [float(bbox["max"][index]) - float(bbox["min"][index]) for index in range(3)]
    measurements = [
        _measurement(scope, "bounding_box_x", spans[0], "bounding_box_axis_span", [scope.id]),
        _measurement(scope, "bounding_box_y", spans[1], "bounding_box_axis_span", [scope.id]),
        _measurement(scope, "bounding_box_z", spans[2], "bounding_box_axis_span", [scope.id]),
    ]
    if axis_feature and axis_feature.axis:
        length = projected_length(bbox, axis_feature.axis)
        measurements.append(_measurement(scope, "overall_length_along_main_axis", length, "axis_projection", axis_feature.source_entity_ids))
        analytic_diameter = _analytic_maximum_diameter(entities, axis_feature.axis)
        if analytic_diameter:
            diameter_value, source_ids = analytic_diameter
            measurements.append(
                _measurement(
                    scope,
                    "maximum_radial_diameter",
                    diameter_value,
                    "analytic_radial_diameter",
                    source_ids,
                )
            )
            return measurements
        measurements.append(
            _measurement(
                scope,
                "maximum_radial_diameter",
                _maximum_radial_diameter(bbox, axis_feature.axis, axis_feature.center or [0.0, 0.0, 0.0]),
                "bounding_box_radial_projection",
                [scope.id],
            )
        )
    return measurements


def _analytic_maximum_diameter(entities: list[EntityFact], axis: list[float]) -> tuple[float, list] | None:
    main_axis = normalize(axis)
    if main_axis is None:
        return None
    candidates = []
    for entity in entities:
        if entity.geometry_type not in {"cylinder", "circle"}:
            continue
        radius = entity.geometry.get("radius")
        entity_axis = entity.geometry.get("axis")
        if radius is None or not isinstance(entity_axis, list):
            continue
        normalized_axis = normalize([float(value) for value in entity_axis])
        if normalized_axis is None:
            continue
        if abs(dot(main_axis, normalized_axis)) < 0.99:
            continue
        candidates.append((float(radius) * 2.0, entity.id))
    if not candidates:
        return None
    diameter = max(value for value, _ in candidates)
    source_ids = [entity_id for value, entity_id in candidates if abs(value - diameter) <= 1e-6]
    return diameter, source_ids


def _maximum_radial_diameter(bbox: dict, axis: list[float], origin: list[float]) -> float:
    mins = bbox["min"]
    maxs = bbox["max"]
    corners = [
        [x, y, z]
        for x in (mins[0], maxs[0])
        for y in (mins[1], maxs[1])
        for z in (mins[2], maxs[2])
    ]
    max_radius = 0.0
    for corner in corners:
        relative = [corner[index] - origin[index] for index in range(3)]
        projection = dot(relative, axis)
        radial = [relative[index] - projection * axis[index] for index in range(3)]
        max_radius = max(max_radius, math.sqrt(sum(component * component for component in radial)))
    return max_radius * 2.0


def _measurement(scope: EntityFact, measurement_type: str, value: float, method: str, source_ids) -> MeasurementFact:
    normalized = round(float(value), 9)
    return MeasurementFact(
        revision_id=scope.revision_id,
        scope_entity_id=scope.id,
        feature_id=None,
        measurement_type=measurement_type,
        raw_value={"value": normalized},
        normalized_value={"value": normalized},
        unit="mm",
        source_entity_ids=list(source_ids),
        method=method,
        confidence=0.75,
    )
