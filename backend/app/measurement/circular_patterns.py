from __future__ import annotations

import math
from collections import defaultdict

from app.measurement.axis_detector import normalize
from app.measurement.schemas import EntityFact, FeatureCandidateFact


def detect_circular_patterns(entities: list[EntityFact], member_features: list[FeatureCandidateFact]) -> list[FeatureCandidateFact]:
    cylinders = [entity for entity in entities if entity.geometry_type == "cylinder" and _circle_ready(entity)]
    circles = [entity for entity in entities if entity.geometry_type == "circle" and _circle_ready(entity)]
    return _detect_patterns(cylinders, member_features) or _detect_patterns(circles, member_features)


def _detect_patterns(circles: list[EntityFact], member_features: list[FeatureCandidateFact]) -> list[FeatureCandidateFact]:
    groups: dict[tuple, list[EntityFact]] = defaultdict(list)
    for circle in circles:
        axis = normalize([float(value) for value in circle.geometry["axis"]])
        radius = round(float(circle.geometry["radius"]), 6)
        scope_id = circle.parent_entity_id or circle.id
        if axis is None:
            continue
        groups[(scope_id, tuple(axis), radius)].append(circle)

    patterns: list[FeatureCandidateFact] = []
    for (scope_id, axis, radius), members in groups.items():
        if len(members) < 3:
            continue
        centers = [member.geometry["center"] for member in members]
        basis_u, basis_v = _plane_basis(list(axis))
        center = _fit_center(centers, basis_u, basis_v)
        radial_distances = [_distance_in_plane(point, center, basis_u, basis_v) for point in centers]
        pitch_radius = sum(radial_distances) / len(radial_distances)
        if pitch_radius <= 1e-9:
            continue
        angles = sorted(_angle_in_plane(point, center, basis_u, basis_v) for point in centers)
        spacings = [(angles[(index + 1) % len(angles)] - angles[index]) % 360.0 for index in range(len(angles))]
        expected = 360.0 / len(angles)
        residual = max(abs(spacing - expected) for spacing in spacings)
        if residual > 5.0:
            continue
        member_feature_ids = [
            str(feature.id)
            for feature in member_features
            if set(feature.source_entity_ids).intersection(member.id for member in members)
        ]
        patterns.append(
            FeatureCandidateFact(
                revision_id=members[0].revision_id,
                scope_entity_id=scope_id,
                feature_type="circular_pattern",
                source_entity_ids=[member.id for member in members],
                parameters={
                    "count": len(members),
                    "member_diameter": round(radius * 2.0, 9),
                    "pitch_circle_diameter": round(pitch_radius * 2.0, 9),
                    "center": [round(value, 9) for value in center],
                    "axis": list(axis),
                    "angular_spacing": round(expected, 9),
                    "start_angle": round(angles[0], 9),
                    "fit_residual": round(residual, 9),
                    "member_feature_ids": member_feature_ids,
                    "source_entity_ids": [str(member.id) for member in members],
                },
                axis=list(axis),
                center=[round(value, 9) for value in center],
                confidence=max(0.3, 0.85 - residual / 10.0),
                algorithm="circular_patterns",
            )
        )
    return patterns


def _circle_ready(entity: EntityFact) -> bool:
    return isinstance(entity.geometry.get("axis"), list) and isinstance(entity.geometry.get("center"), list) and entity.geometry.get("radius") is not None


def _plane_basis(axis: list[float]) -> tuple[list[float], list[float]]:
    reference = [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0]
    basis_u = _normalize(_cross(axis, reference))
    basis_v = _normalize(_cross(axis, basis_u))
    return basis_u, basis_v


def _fit_center(points: list[list[float]], basis_u: list[float], basis_v: list[float]) -> list[float]:
    mean = [sum(float(point[index]) for point in points) / len(points) for index in range(3)]
    return [round(value, 9) for value in mean]


def _distance_in_plane(point: list[float], center: list[float], basis_u: list[float], basis_v: list[float]) -> float:
    relative = [float(point[index]) - float(center[index]) for index in range(3)]
    u = sum(relative[index] * basis_u[index] for index in range(3))
    v = sum(relative[index] * basis_v[index] for index in range(3))
    return math.sqrt(u * u + v * v)


def _angle_in_plane(point: list[float], center: list[float], basis_u: list[float], basis_v: list[float]) -> float:
    relative = [float(point[index]) - float(center[index]) for index in range(3)]
    u = sum(relative[index] * basis_u[index] for index in range(3))
    v = sum(relative[index] * basis_v[index] for index in range(3))
    return math.degrees(math.atan2(v, u)) % 360.0


def _cross(left: list[float], right: list[float]) -> list[float]:
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(component * component for component in vector))
    return [component / length for component in vector]
