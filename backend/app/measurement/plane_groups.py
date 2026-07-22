from __future__ import annotations

import math

from app.measurement.axis_detector import normalize
from app.measurement.schemas import EntityFact, MeasurementFact


def build_parallel_plane_measurements(entities: list[EntityFact]) -> list[MeasurementFact]:
    planes = [entity for entity in entities if entity.geometry_type == "plane" and isinstance(entity.geometry.get("normal"), list)]
    measurements: list[MeasurementFact] = []
    for left_index, left in enumerate(planes):
        left_normal = normalize([float(value) for value in left.geometry["normal"]])
        left_position = left.geometry.get("position")
        if left_normal is None or not isinstance(left_position, list):
            continue
        for right in planes[left_index + 1 :]:
            right_normal = normalize([float(value) for value in right.geometry["normal"]])
            right_position = right.geometry.get("position")
            if right_normal != left_normal or not isinstance(right_position, list):
                continue
            distance = abs(sum((float(right_position[index]) - float(left_position[index])) * left_normal[index] for index in range(3)))
            if distance <= 1e-9:
                continue
            measurements.append(
                MeasurementFact(
                    revision_id=left.revision_id,
                    scope_entity_id=left.parent_entity_id or left.id,
                    feature_id=None,
                    measurement_type="parallel_plane_distance",
                    raw_value={"value": round(distance, 9)},
                    normalized_value={"value": round(distance, 9)},
                    unit="mm",
                    source_entity_ids=[left.id, right.id],
                    method="parallel_plane_offset",
                    confidence=0.8,
                    metadata={"normal": left_normal},
                )
            )
    return measurements
