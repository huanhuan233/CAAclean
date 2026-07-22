from __future__ import annotations

import math
from collections import defaultdict

from app.measurement.schemas import EntityFact, FeatureCandidateFact


AXIAL_TYPES = {"cylinder", "cone", "torus"}


def normalize(vector: list[float]) -> list[float] | None:
    length = math.sqrt(sum(component * component for component in vector))
    if length == 0:
        return None
    normalized = [component / length for component in vector]
    first_nonzero = next((component for component in normalized if abs(component) > 1e-9), 0.0)
    if first_nonzero < 0:
        normalized = [-component for component in normalized]
    return [round(component, 9) for component in normalized]


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def detect_main_axis(entities: list[EntityFact]) -> FeatureCandidateFact | None:
    candidates = []
    for entity in entities:
        if entity.geometry_type not in AXIAL_TYPES:
            continue
        axis = entity.geometry.get("axis")
        if not isinstance(axis, list) or len(axis) != 3:
            continue
        normalized = normalize([float(value) for value in axis])
        if normalized is None:
            continue
        candidates.append((entity, normalized))

    if not candidates:
        return _detect_bounding_box_axis(entities)

    groups: dict[tuple[float, float, float], list[EntityFact]] = defaultdict(list)
    for entity, axis in candidates:
        groups[tuple(axis)].append(entity)

    axis_key, members = max(
        groups.items(),
        key=lambda item: (sum(float(entity.area or 0.0) for entity in item[1]), len(item[1])),
    )
    axis = list(axis_key)
    centers = [entity.center or entity.geometry.get("center") for entity in members if entity.center or entity.geometry.get("center")]
    origin = _average(centers) if centers else [0.0, 0.0, 0.0]
    scope = _scope_for(members[0], entities)
    support_ratio = len(members) / max(1, len(candidates))
    confidence = min(0.95, 0.45 + support_ratio * 0.35 + min(0.15, len(members) * 0.03))
    return FeatureCandidateFact(
        revision_id=members[0].revision_id,
        scope_entity_id=scope.id,
        feature_type="main_axis_candidate",
        source_entity_ids=[entity.id for entity in members],
        parameters={"axis_origin": origin, "supporting_entity_ids": [str(entity.id) for entity in members]},
        axis=axis,
        center=origin,
        confidence=round(confidence, 6),
        algorithm="axis_detector",
    )


def _detect_bounding_box_axis(entities: list[EntityFact]) -> FeatureCandidateFact | None:
    scope = next((entity for entity in entities if entity.entity_type == "solid" and entity.bounding_box), None)
    if scope is None:
        scope = next((entity for entity in entities if entity.bounding_box), None)
    if scope is None or scope.bounding_box is None:
        return None
    spans = [float(scope.bounding_box["max"][index]) - float(scope.bounding_box["min"][index]) for index in range(3)]
    axis_index = max(range(3), key=lambda index: spans[index])
    axis = [0.0, 0.0, 0.0]
    axis[axis_index] = 1.0
    origin = [
        (float(scope.bounding_box["min"][index]) + float(scope.bounding_box["max"][index])) / 2.0
        for index in range(3)
    ]
    confidence = 0.35 if spans[axis_index] > 0 else 0.1
    return FeatureCandidateFact(
        revision_id=scope.revision_id,
        scope_entity_id=scope.id,
        feature_type="main_axis_candidate",
        source_entity_ids=[scope.id],
        parameters={"axis_origin": origin, "supporting_entity_ids": [str(scope.id)], "basis": "bounding_box_longest_span"},
        axis=axis,
        center=origin,
        confidence=confidence,
        algorithm="axis_detector",
    )


def _average(points: list[list[float]]) -> list[float]:
    return [sum(point[index] for point in points) / len(points) for index in range(3)]


def _scope_for(entity: EntityFact, entities: list[EntityFact]) -> EntityFact:
    by_id = {item.id: item for item in entities}
    current = entity
    while current.parent_entity_id and current.parent_entity_id in by_id:
        parent = by_id[current.parent_entity_id]
        if parent.entity_type == "solid":
            return parent
        current = parent
    return current


def projected_length(bounding_box: dict, axis: list[float]) -> float:
    mins = bounding_box["min"]
    maxs = bounding_box["max"]
    corners = [
        [x, y, z]
        for x in (mins[0], maxs[0])
        for y in (mins[1], maxs[1])
        for z in (mins[2], maxs[2])
    ]
    projections = [dot(corner, axis) for corner in corners]
    return max(projections) - min(projections)
