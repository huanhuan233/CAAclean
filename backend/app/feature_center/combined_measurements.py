"""Derive bounded relations from already recognized features and their roles."""

from __future__ import annotations

import math
from typing import Any

from .contracts import Measurement, stable_id
from .eaag import EaagGraph


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _sub(a, b):
    return [x-y for x, y in zip(a, b)]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _add(a, b):
    return [x+y for x, y in zip(a, b)]


def _scale(a, factor):
    return [x*factor for x in a]


def _normal(face: dict[str, Any]):
    samples = (face.get("geometry") or {}).get("normal_samples") or []
    return samples[0] if samples and isinstance(samples[0], list) and len(samples[0]) == 3 else None


def _inner_fillet_role(feature, graph: EaagGraph, solid_faces: set[str], tolerance: float):
    payload = feature.typed_payload.get("geometry_recognition") or {}
    if feature.family != "fillet" or payload.get("convexity") != "concave":
        return
    support_ids = payload.get("support_face_ids") or []
    if len(support_ids) != 2:
        return
    candidates = []
    for support_id in support_ids:
        support = graph.entities[support_id]
        normal = _normal(support)
        if normal is None:
            continue
        distances = []
        for face_id in solid_faces:
            other = graph.entities[face_id]
            other_normal = _normal(other)
            if (face_id == support_id or other.get("geometry_type") != "plane" or
                other_normal is None or _dot(normal, other_normal) < 1-1e-3 or
                float(other.get("area") or 0) <= float(support.get("area") or 0)):
                continue
            distance = _dot(_sub(other["center"], support["center"]), normal)
            if distance > tolerance:
                distances.append((distance, face_id))
        if distances:
            candidates.append((min(distances), support_id))
    if not candidates:
        payload["cavity_role_status"] = "unverified_no_opening_support"
        return
    candidates.sort()
    if len(candidates) > 1 and abs(candidates[0][0][0]-candidates[1][0][0]) <= tolerance:
        payload["cavity_role_status"] = "candidate_ambiguous_support"
        return
    (_, opening_id), floor_id = candidates[0]
    wall_id = next(face_id for face_id in support_ids if face_id != floor_id)
    payload.update({"cavity_role": "inner_bottom_fillet_candidate",
                    "cavity_role_status": "candidate",
                    "cavity_floor_face_id": floor_id, "cavity_wall_face_id": wall_id,
                    "cavity_opening_support_face_id": opening_id,
                    "role_method": "concave_analytic_transition_and_nearest_parallel_opening_plane"})
    feature.diagnostics.append("CAVITY_REGION_NOT_INDEPENDENTLY_CLOSED")


def _center_path(feature, graph: EaagGraph, tolerance: float, result):
    payload = feature.typed_payload.get("geometry_recognition") or {}
    if feature.family != "fillet" or feature.subtype != "constant_radius_straight_edge":
        return
    face_ids = payload.get("transition_face_ids") or []
    if len(face_ids) != 1:
        return
    face = graph.entities[face_ids[0]]
    evidence = (face.get("geometry") or {}).get("recognition_evidence") or {}
    axial = evidence.get("axial_range_mm")
    if not isinstance(axial, list) or len(axial) != 2:
        return
    length = abs(float(axial[1])-float(axial[0]))
    if length <= tolerance:
        return
    payload["center_path_length_mm"] = length
    payload["center_path_length_definition"] = "analytic_cylinder_axis_between_bounded_transition_ends"
    payload["support_boundary_length_mm"] = payload.get("path_length_mm")
    result.measurements.append(Measurement(
        measurement_id=stable_id("MEAS", feature.feature_center_id, "center_path_length"),
        feature_center_id=feature.feature_center_id, name="center_path_length", value=length,
        unit="mm", tolerance=tolerance, source="geometry_recognition",
        method="bounded_transition_cylinder_axis_projection", algorithm_version="p4c_combined.v1",
        input_face_ids=face_ids, validity="valid"))


def _boss_rib_distance(boss, rib, graph: EaagGraph, tolerance: float):
    boss_payload = boss.typed_payload.get("geometry_recognition") or {}
    rib_payload = rib.typed_payload.get("geometry_recognition") or {}
    if (boss.subtype != "circular_straight_wall" or rib.family != "rib" or
        boss.geometry_refs.solid_ids != rib.geometry_refs.solid_ids or
        boss_payload.get("support_face_id") != rib_payload.get("root_support_face_id")):
        return None
    parent_id = rib_payload.get("parent_geometry_feature_id")
    if not parent_id:
        return None
    center = graph.entities[boss_payload["cap_face_id"]]["center"]
    frame = rib.coordinate_frame
    rib_center = frame["origin_mm"]
    x_axis, y_axis, normal = frame["x_axis"], frame["y_axis"], frame["normal"]
    boss_normal = boss.coordinate_frame.get("normal")
    if boss_normal is None or _dot(normal, boss_normal) < 1-1e-3:
        return None
    boss_height = float(boss_payload["height_mm"])
    rib_height = float(rib_payload["height_mm"])
    boss_top, rib_top = _dot(center, normal), _dot(rib_center, normal)
    overlap_low = max(boss_top-boss_height, rib_top-rib_height)
    overlap_high = min(boss_top, rib_top)
    if overlap_high-overlap_low <= tolerance:
        return None
    delta = _sub(center, rib_center)
    x, y = _dot(delta, x_axis), _dot(delta, y_axis)
    half_length, half_width = float(rib_payload["length_mm"])/2, float(rib_payload["local_thickness_mm"])/2
    qx = max(-half_length, min(half_length, x))
    qy = max(-half_width, min(half_width, y))
    dx, dy = qx-x, qy-y
    radial = math.hypot(dx, dy)
    radius = float(boss_payload["diameter_mm"])/2
    if radial <= radius+tolerance:
        return {"status": "overlap_or_contact", "distance_mm": 0.0,
                "method": "analytic_cylinder_to_rectangular_prism_body_scope"}
    level = (overlap_low+overlap_high)/2
    circle_point = _add(_add(center, _scale(normal, level-boss_top)),
                        _add(_scale(x_axis, dx/radial*radius), _scale(y_axis, dy/radial*radius)))
    rib_point = _add(_add(rib_center, _scale(normal, level-rib_top)),
                     _add(_scale(x_axis, qx), _scale(y_axis, qy)))
    return {"status": "measured", "distance_mm": radial-radius,
            "start_point_mm": circle_point, "end_point_mm": rib_point,
            "scope": "circular_boss_wall_to_rectangular_rib_body_excluding_root_and_fillets",
            "method": "analytic_circle_to_finite_rectangle_with_overlapping_height"}


def apply_combined_measurements(result, graph: EaagGraph, tolerance: float) -> None:
    """Consume current features only; all outputs retain their own input IDs."""
    solid_faces = {}
    for relation in graph.relations:
        if relation["relation_type"] == "has_face" and graph.entities.get(relation["source_entity_id"], {}).get("entity_type") == "solid":
            solid_faces.setdefault(relation["source_entity_id"], set()).add(relation["target_entity_id"])
    for feature in result.canonical_features:
        _center_path(feature, graph, tolerance, result)
        if feature.geometry_refs.solid_ids:
            _inner_fillet_role(feature, graph, solid_faces.get(feature.geometry_refs.solid_ids[0], set()), tolerance)
    bosses = [feature for feature in result.canonical_features if feature.family == "boss"
              and feature.subtype == "circular_straight_wall"]
    ribs = [feature for feature in result.canonical_features if feature.family == "rib"]
    for rib in ribs:
        for boss in bosses[:128]:
            relation = _boss_rib_distance(boss, rib, graph, tolerance)
            if relation is None:
                continue
            relation["boss_feature_id"] = boss.feature_center_id
            relation["rib_feature_id"] = rib.feature_center_id
            rib.typed_payload["geometry_recognition"].setdefault("combined_measurements", []).append(relation)
            rib.relations.append({"kind": "MEASURED_TO", "target_id": boss.feature_center_id})
            result.measurements.append(Measurement(
                measurement_id=stable_id("MEAS", rib.feature_center_id, boss.feature_center_id, "boss_to_rib_shortest"),
                feature_center_id=rib.feature_center_id, name="boss_to_rib_shortest_distance",
                value=relation["distance_mm"], unit="mm", tolerance=tolerance,
                source="geometry_recognition", method=relation["method"],
                algorithm_version="p4c_combined.v1",
                input_face_ids=sorted(set(boss.geometry_refs.face_ids + rib.geometry_refs.face_ids)),
                validity="valid" if relation["status"] == "measured" else "needs_review"))
