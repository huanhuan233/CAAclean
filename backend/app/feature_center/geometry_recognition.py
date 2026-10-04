"""Conservative, history-independent recognition from one parsed Solid snapshot."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .contracts import CanonicalFeature, GeometryRefs, Measurement, Observation, stable_id
from .eaag import EaagGraph
from .standard_structures import circular_bosses, planar_structures
from .thin_structures import structural_proposals

RULE_VERSION = "geometry_p4b_thin_structures.v3"


@dataclass
class RecognitionResult:
    observations: list[Observation] = field(default_factory=list)
    canonical_features: list[CanonicalFeature] = field(default_factory=list)
    feature_geometry_links: list[dict[str, Any]] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x*y for x, y in zip(a, b))


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [x-y for x, y in zip(a, b)]


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _line_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    axis = first["axis"]
    delta = _sub(second["origin"], first["origin"])
    return _norm(_sub(delta, [component*_dot(delta, axis) for component in axis]))


def _common_angular_bins(group: list[dict[str, Any]], axis: list[float]) -> set[int] | None:
    """Rebin world-space directions; face UV bins have unrelated zero angles."""
    reference_axis = [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0]
    reference = [axis[1]*reference_axis[2]-axis[2]*reference_axis[1],
                 axis[2]*reference_axis[0]-axis[0]*reference_axis[2],
                 axis[0]*reference_axis[1]-axis[1]*reference_axis[0]]
    reference = [value/_norm(reference) for value in reference]
    perpendicular = [axis[1]*reference[2]-axis[2]*reference[1],
                     axis[2]*reference[0]-axis[0]*reference[2],
                     axis[0]*reference[1]-axis[1]*reference[0]]
    bins: set[int] = set()
    for wall in group:
        samples = wall["evidence"].get("angular_sample_directions")
        if not isinstance(samples, list) or not samples:
            return None
        for sample in samples:
            if not isinstance(sample, list) or len(sample) != 3:
                return None
            try:
                direction = [float(value) for value in sample]
            except (TypeError, ValueError):
                return None
            if not all(math.isfinite(value) for value in direction) or abs(_norm(direction)-1) > 1e-3:
                return None
            angle = math.atan2(_dot(direction, perpendicular), _dot(direction, reference)) % (2*math.pi)
            bins.add(min(35, int(angle*36/(2*math.pi))))
    return bins


def _normalized_wall(face: dict[str, Any]) -> dict[str, Any] | None:
    geometry = face.get("geometry") or {}
    evidence = geometry.get("recognition_evidence") or {}
    if face.get("geometry_type") != "cylinder" or evidence.get("status") != "evaluated":
        return None
    try:
        axis = [float(value) for value in evidence["axis_unit"]]
        origin = [float(value) for value in geometry["center"]]
        radius = float(geometry["radius"])
        low, high = [float(value) for value in evidence["axial_range_mm"]]
        coverage = float(evidence["angular_coverage_rad"])
        if len(axis) != 3 or len(origin) != 3 or not all(math.isfinite(v) for v in axis+origin+[radius,low,high,coverage]):
            return None
        if radius <= 0 or high <= low or abs(_norm(axis)-1) > 1e-4:
            return None
        reversed_axis = next((value for value in axis if abs(value) > 1e-8), 1) < 0
        end_states = list(evidence.get("end_states") or [])
        end_scan = list(evidence.get("end_scan") or [])
        if reversed_axis:
            axis = [-value for value in axis]
            low, high = -high, -low
            end_states.reverse()
            end_scan.reverse()
        endpoints = [[origin[i]+axis[i]*t for i in range(3)] for t in (low, high)]
        return {"face": face, "axis": axis, "origin": origin, "radius": radius,
                "start": endpoints[0], "end": endpoints[1], "coverage": coverage,
                "end_states": end_states, "end_scan": end_scan,
                "side": evidence.get("radial_material_side"), "evidence": evidence,
                "reversed_axis": reversed_axis}
    except (KeyError, TypeError, ValueError):
        return None


def _solid_faces(graph: EaagGraph) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for relation in graph.relations:
        if relation["relation_type"] == "has_face" and graph.entities.get(relation["source_entity_id"], {}).get("entity_type") == "solid":
            result[relation["source_entity_id"]].append(relation["target_entity_id"])
    return {key: sorted(value) for key, value in result.items()}


def _plane(face: dict[str, Any]) -> tuple[list[float], list[float]] | None:
    geometry = face.get("geometry") or {}
    if face.get("geometry_type") != "plane":
        return None
    try:
        normal = [float(x) for x in geometry["normal"]]
        point = [float(x) for x in geometry["position"]]
        length = _norm(normal)
        return ([x/length for x in normal], point) if length > 1e-8 else None
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def _shared_lines(graph: EaagGraph, left: str, right: str) -> list[dict[str, Any]]:
    return [graph.entities[edge_id] for edge_id in graph.shared_edge_ids(left, right)
            if graph.entities.get(edge_id, {}).get("geometry_type") == "line"]


def _shared_circles(graph: EaagGraph, left: str, right: str) -> list[dict[str, Any]]:
    return [graph.entities[edge_id] for edge_id in graph.shared_edge_ids(left, right)
            if graph.entities.get(edge_id, {}).get("geometry_type") == "circle"]


def _line_points(edge: dict[str, Any]) -> list[list[float]]:
    geometry = edge.get("geometry") or {}
    points = [geometry.get("start_point"), geometry.get("end_point")]
    return points if all(isinstance(point, list) and len(point) == 3 for point in points) else []


def _recognize_transitions(result: RecognitionResult, part_id: str, graph: EaagGraph,
                           solid_id: str, face_ids: list[str], tolerance: float,
                           shape_hash: str) -> None:
    for face_id in face_ids:
        face = graph.entities[face_id]
        surface = face.get("geometry_type")
        if surface not in ("cylinder", "plane", "torus", "cone"):
            continue
        neighbors = [neighbor for neighbor in graph.face_neighbors(face_id)
                     if neighbor in face_ids and _plane(graph.entities[neighbor])]
        supports = []
        for neighbor in neighbors:
            lines = _shared_lines(graph, face_id, neighbor)
            if lines:
                supports.append((neighbor, lines[0]))
        if surface == "cylinder":
            wall = _normalized_wall(face)
            if not wall or wall["side"] == "inner_wall" or wall["coverage"] >= math.pi + 0.05:
                continue
            for first_index in range(len(supports)):
                for second_index in range(first_index+1, len(supports)):
                    first_id, first_edge = supports[first_index]
                    second_id, second_edge = supports[second_index]
                    first_plane = _plane(graph.entities[first_id])
                    second_plane = _plane(graph.entities[second_id])
                    if not first_plane or not second_plane:
                        continue
                    checks = []
                    for support_plane, edge in ((first_plane, first_edge), (second_plane, second_edge)):
                        normal, position = support_plane
                        distance = abs(_dot(normal, _sub(wall["origin"], position)))
                        points = _line_points(edge)
                        parallel = bool(points) and abs(_dot([v/_norm(_sub(points[1], points[0])) for v in _sub(points[1], points[0])], wall["axis"])) > 1-1e-3 if points and _norm(_sub(points[1], points[0])) > 1e-8 else False
                        checks.append((abs(distance-wall["radius"]), parallel))
                    if not all(residual <= tolerance and parallel for residual, parallel in checks):
                        continue
                    support_ids = sorted([first_id, second_id])
                    payload = {"radius_mm": wall["radius"], "transition_face_ids": [face_id],
                               "support_face_ids": support_ids, "tangency_residuals_mm": [item[0] for item in checks],
                               "tangency_method": "analytic_plane_cylinder_distance_and_shared_finite_edges",
                               "convexity": "unknown", "path_length_mm": min(float(first_edge.get("length") or 0), float(second_edge.get("length") or 0)),
                               "path_length_definition": "shorter_support_boundary_edge"}
                    _record(result, part_id, shape_hash, solid_id, "fillet", "constant_radius_straight_edge",
                            {"transition": [face_id], "support": support_ids}, payload, "confirmed", [],
                            [("radius", wall["radius"], "mm", "analytic_cylinder_radius")], tolerance)
                    break
                else:
                    continue
                break

        elif surface == "cone":
            geometry = face.get("geometry") or {}
            try:
                cone_axis = [float(value) for value in geometry["axis"]]
                cone_origin = [float(value) for value in geometry["center"]]
                if abs(_norm(cone_axis)-1) > 1e-4:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            cylinders = [neighbor for neighbor in graph.face_neighbors(face_id) if neighbor in face_ids
                         and _normalized_wall(graph.entities[neighbor]) is not None]
            planes = [neighbor for neighbor in graph.face_neighbors(face_id) if neighbor in face_ids
                      and _plane(graph.entities[neighbor]) is not None]
            for cylinder_id in cylinders:
                wall = _normalized_wall(graph.entities[cylinder_id])
                if not wall or wall["side"] != "inner_wall" or abs(_dot(wall["axis"], cone_axis)) < 1-1e-4:
                    continue
                if _line_distance(wall, {"origin": cone_origin}) > tolerance:
                    continue
                cylinder_edges = _shared_circles(graph, face_id, cylinder_id)
                if len(cylinder_edges) != 1:
                    continue
                cylinder_edge = cylinder_edges[0]
                for plane_id in planes:
                    plane_edges = _shared_circles(graph, face_id, plane_id)
                    if len(plane_edges) != 1:
                        continue
                    plane_edge = plane_edges[0]
                    try:
                        cylinder_radius = float(cylinder_edge["geometry"]["radius"])
                        plane_radius = float(plane_edge["geometry"]["radius"])
                        cylinder_center = [float(value) for value in cylinder_edge["center"]]
                        plane_center = [float(value) for value in plane_edge["center"]]
                    except (KeyError, TypeError, ValueError):
                        continue
                    axial = abs(_dot(_sub(plane_center, cylinder_center), wall["axis"]))
                    radial = abs(plane_radius-cylinder_radius)
                    if (axial <= tolerance or radial <= tolerance or
                        abs(cylinder_radius-wall["radius"]) > tolerance or
                        _line_distance(wall, {"origin": plane_center}) > tolerance or
                        abs(_norm(_sub(plane_center, cylinder_center))-axial) > tolerance):
                        continue
                    plane = _plane(graph.entities[plane_id])
                    if not plane or abs(_dot(plane[0], wall["axis"])) < 1-1e-3:
                        continue
                    angle = math.degrees(math.atan2(radial, axial))
                    payload = {"mode": "circular_mouth_cone", "axial_distance_mm": axial,
                               "radial_distance_mm": radial, "angle_deg": angle,
                               "angle_definition": "cone_profile_to_cylinder_axis",
                               "support_face_ids": [plane_id, cylinder_id],
                               "transition_face_ids": [face_id],
                               "measurement_section": "axial_plane_through_cone_axis",
                               "manufacturing_intent": "not_evaluated"}
                    _record(result, part_id, shape_hash, solid_id, "chamfer", "circular_hole_mouth_cone",
                            {"transition": [face_id], "support": [plane_id, cylinder_id]},
                            payload, "confirmed", [],
                            [("axial_distance", axial, "mm", "circle_center_axis_projection"),
                             ("radial_distance", radial, "mm", "shared_circle_radius_difference"),
                             ("angle", angle, "deg", "cone_profile_to_cylinder_axis")], tolerance)
                    break
                else:
                    continue
                break
        elif surface == "plane" and len(supports) >= 2:
            transition = _plane(face)
            if not transition:
                continue
            for first_index in range(len(supports)):
                for second_index in range(first_index+1, len(supports)):
                    first_id, first_edge = supports[first_index]
                    second_id, second_edge = supports[second_index]
                    plane1, plane2 = _plane(graph.entities[first_id]), _plane(graph.entities[second_id])
                    if not plane1 or not plane2:
                        continue
                    transition_area = float(face.get("area") or 0)
                    if transition_area <= 0 or transition_area >= min(float(graph.entities[first_id].get("area") or 0),
                                                                         float(graph.entities[second_id].get("area") or 0)):
                        continue
                    n1, p1 = plane1
                    n2, p2 = plane2
                    cosine = _dot(n1, n2)
                    sine = math.sqrt(max(0, 1-cosine*cosine))
                    edge1, edge2 = _line_points(first_edge), _line_points(second_edge)
                    if sine < 0.15 or not edge1 or not edge2:
                        continue
                    d1_values = [abs(_dot(n2, _sub(point, p2)))/sine for point in edge1]
                    d2_values = [abs(_dot(n1, _sub(point, p1)))/sine for point in edge2]
                    d1, d2 = sum(d1_values)/2, sum(d2_values)/2
                    residual = max(abs(d1_values[0]-d1_values[1]), abs(d2_values[0]-d2_values[1]))
                    if d1 <= tolerance or d2 <= tolerance or residual > tolerance:
                        continue
                    direction1 = _sub(edge1[1], edge1[0])
                    direction2 = _sub(edge2[1], edge2[0])
                    if _norm(direction1) < 1e-8 or _norm(direction2) < 1e-8 or abs(_dot(direction1, direction2)/(_norm(direction1)*_norm(direction2))) < 1-1e-3:
                        continue
                    # The transition plane must touch both finite shared edges.
                    tn, tp = transition
                    if abs(_dot(tn, n1)) > 0.98 or abs(_dot(tn, n2)) > 0.98:
                        continue
                    if max(abs(_dot(tn, _sub(point, tp))) for point in edge1+edge2) > tolerance:
                        continue
                    support_ids = sorted([first_id, second_id])
                    angle = math.degrees(math.acos(min(1, abs(_dot(tn, n1)))))
                    payload = {"mode": "two_distances", "d1_mm": d1, "d2_mm": d2,
                               "angle_deg": angle, "angle_definition": "acute_angle_between_transition_and_first_support_planes",
                               "support_face_ids": [first_id, second_id], "transition_face_ids": [face_id],
                               "virtual_sharp_edge": "intersection_of_support_planes",
                               "measurement_section": "normal_to_parallel_shared_edges", "consistency_residual_mm": residual,
                               "manufacturing_intent": "not_evaluated"}
                    _record(result, part_id, shape_hash, solid_id, "chamfer", "straight_edge_two_plane",
                            {"transition": [face_id], "support": support_ids}, payload, "confirmed", [],
                            [("d1", d1, "mm", "plane_distance_in_normal_section"),
                             ("d2", d2, "mm", "plane_distance_in_normal_section"),
                             ("angle", angle, "deg", "angle_between_transition_and_first_support_planes")], tolerance)
                    break
                else:
                    continue
                break


def _combine_step_segments(result: RecognitionResult, part_id: str, graph: EaagGraph,
                           solid_id: str, tolerance: float, shape_hash: str) -> None:
    holes = [feature for feature in result.canonical_features if feature.family == "hole"
             and feature.review_state == "auto_verified"
             and feature.geometry_refs.solid_ids == [solid_id]]
    parents = list(range(len(holes)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for left in range(len(holes)):
        a = holes[left].typed_payload["geometry_recognition"]
        for right in range(left+1, len(holes)):
            b = holes[right].typed_payload["geometry_recognition"]
            if abs(a["diameter_mm"]-b["diameter_mm"]) <= tolerance:
                continue
            if _dot(a["axis_direction"], b["axis_direction"]) < 1-1e-4:
                continue
            if _line_distance({"axis": a["axis_direction"], "origin": a["axis_point_mm"]},
                              {"origin": b["axis_point_mm"]}) > tolerance:
                continue
            joins = ((a["end_point_mm"], a["end_states"][1], b["start_point_mm"], b["end_states"][0]),
                     (b["end_point_mm"], b["end_states"][1], a["start_point_mm"], a["end_states"][0]))
            if any(_norm(_sub(one, two)) <= tolerance and state_one == state_two == "void"
                   for one, state_one, two, state_two in joins):
                parents[root(right)] = root(left)
    components: dict[int, list[CanonicalFeature]] = defaultdict(list)
    for index, feature in enumerate(holes):
        components[root(index)].append(feature)
    for members in components.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda feature: _dot(feature.typed_payload["geometry_recognition"]["start_point_mm"],
                                              feature.typed_payload["geometry_recognition"]["axis_direction"]))
        segments = [feature.typed_payload["geometry_recognition"] for feature in members]
        old_ids = {feature.feature_center_id for feature in members}
        old_observation_ids = {identifier for feature in members for identifier in feature.source_observation_ids}
        result.canonical_features = [feature for feature in result.canonical_features if feature.feature_center_id not in old_ids]
        result.observations = [observation for observation in result.observations if observation.observation_id not in old_observation_ids]
        result.measurements = [measure for measure in result.measurements if measure.feature_center_id not in old_ids]
        result.feature_geometry_links = [link for link in result.feature_geometry_links if link["feature_center_id"] not in old_ids]
        face_ids = sorted({face_id for feature in members for face_id in feature.geometry_refs.face_ids})
        transition_ids = sorted(set(graph.face_neighbors(face_ids[0])).intersection(*(
            set(graph.face_neighbors(face_id)) for face_id in face_ids[1:]
        ))) if len(face_ids) == 2 else []
        transition_ids = [face_id for face_id in transition_ids
                          if graph.entities.get(face_id, {}).get("geometry_type") == "plane"]
        end_states = [segments[0]["end_states"][0], segments[-1]["end_states"][1]]
        subtype = "stepped_through_hole" if end_states == ["void", "void"] else "stepped_blind_hole"
        payload = {"subtype": subtype, "segments": segments, "axis_direction": segments[0]["axis_direction"],
                   "axis_point_mm": segments[0]["axis_point_mm"], "end_states": end_states,
                   "step_transition_face_ids": transition_ids, "segment_count": len(segments),
                   "classification_status": "confirmed", "render_range_status": "confirmed",
                   "native_history_attribution": "not_evaluated"}
        _record(result, part_id, shape_hash, solid_id, "hole", subtype,
                {"body_wall": face_ids, "step_transition": transition_ids}, payload,
                "confirmed", [], [], tolerance)


def _link(result: RecognitionResult, feature_id: str, face_id: str, role: str) -> None:
    result.feature_geometry_links.append({
        "link_id": stable_id("FGL", feature_id, face_id, role),
        "feature_center_id": feature_id, "face_id": face_id,
        "role": role, "source": "geometry_recognition",
    })


def _record(result: RecognitionResult, part_id: str, shape_hash: str, solid_id: str,
            family: str, subtype: str, face_roles: dict[str, list[str]], payload: dict[str, Any],
            status: str, diagnostics: list[str], measures: list[tuple[str, float, str, str]],
            tolerance: float, measurements_verified: bool = False) -> CanonicalFeature:
    face_ids = sorted(set(face_id for ids in face_roles.values() for face_id in ids))
    feature_id = stable_id("FC", shape_hash, solid_id, family, subtype, *face_ids)
    observation_id = stable_id("OBS", feature_id, RULE_VERSION)
    result.observations.append(Observation(
        observation_id=observation_id, part_id=part_id, source_kind="geometry_recognition",
        source_id=RULE_VERSION, source_version=RULE_VERSION, proposed_family=family,
        proposed_subtype=subtype, geometry_refs=GeometryRefs(face_ids=face_ids, solid_ids=[solid_id]),
        classification_confidence=1.0 if status == "confirmed" else 0.5,
        localization_confidence=1.0, measurement_confidence=1.0 if status == "confirmed" or measurements_verified else 0.5,
        status=status, diagnostics=diagnostics,
    ))
    feature = CanonicalFeature(
        feature_center_id=feature_id, part_id=part_id, family=family, subtype=subtype,
        source_observation_ids=[observation_id], geometry_refs=GeometryRefs(face_ids=face_ids, solid_ids=[solid_id]),
        typed_payload={"geometry_recognition": payload, "geometry_verification": {"status": status,
                       "rule_version": RULE_VERSION, "unmet_conditions": diagnostics}},
        review_state="auto_verified" if status == "confirmed" else "needs_review",
        provenance={"source": "geometry_recognition", "geometry_source": "exported_step_geometry",
                    "native_history_attribution": "not_evaluated", "shape_hash": shape_hash,
                    "rule_version": RULE_VERSION, "tolerance_mm": tolerance},
        diagnostics=diagnostics,
    )
    result.canonical_features.append(feature)
    for role, ids in face_roles.items():
        for face_id in ids:
            _link(result, feature_id, face_id, role)
    for name, value, unit, method in measures:
        result.measurements.append(Measurement(
            measurement_id=stable_id("MEAS", feature_id, name), feature_center_id=feature_id,
            name=name, value=value, unit=unit, tolerance=tolerance, source="geometry_recognition",
            method=method, algorithm_version=RULE_VERSION, input_face_ids=face_ids,
            validity="valid" if status == "confirmed" or measurements_verified else "needs_review",
        ))
    return feature


def recognize_geometry(part_id: str, graph: EaagGraph, tolerance: float, shape_hash: str,
                       thin_wall_pairs: list[dict[str, Any]] | None = None) -> RecognitionResult:
    """Classify bounded inner cylindrical wall groups; never rely on native features."""
    result = RecognitionResult()
    for solid_id, face_ids in _solid_faces(graph).items():
        if len(face_ids) > 5000 or sum(graph.entities[face_id].get("geometry_type") == "cylinder"
                                       for face_id in face_ids) > 256:
            result.diagnostics.append({"code": "GEOMETRY_RECOGNITION_CANDIDATE_LIMIT",
                                       "solid_id": solid_id, "status": "not_evaluated",
                                       "reason": "Solid exceeds 5000 faces or 256 cylinders"})
            continue
        for face_id in face_ids:
            face = graph.entities[face_id]
            if face.get("geometry_type") != "cylinder":
                continue
            evidence = (face.get("geometry") or {}).get("recognition_evidence") or {}
            if evidence.get("status") != "evaluated":
                result.diagnostics.append({"code": "CYLINDER_RECOGNITION_UNEVALUATED",
                                           "solid_id": solid_id, "face_id": face_id,
                                           "status": evidence.get("status", "missing")})
        walls = [_normalized_wall(graph.entities[face_id]) for face_id in face_ids]
        walls = [wall for wall in walls if wall and wall["side"] == "inner_wall"]
        walls.sort(key=lambda wall: wall["face"]["entity_id"])
        parents = list(range(len(walls)))

        def root(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        for left in range(len(walls)):
            for right in range(left+1, len(walls)):
                a, b = walls[left], walls[right]
                if _dot(a["axis"], b["axis"]) < 1-1e-4 or abs(a["radius"]-b["radius"]) > tolerance:
                    continue
                if _line_distance(a, b) > tolerance or not graph.shared_edge_ids(a["face"]["entity_id"], b["face"]["entity_id"]):
                    continue
                if max(_dot(a["start"], a["axis"]), _dot(b["start"], a["axis"])) > min(_dot(a["end"], a["axis"]), _dot(b["end"], a["axis"])) + tolerance:
                    continue
                parents[root(right)] = root(left)
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for index, wall in enumerate(walls):
            groups[root(index)].append(wall)
        for group in groups.values():
            basis = group[0]
            axis = basis["axis"]
            endpoints = [point for wall in group for point in (wall["start"], wall["end"])]
            low = min(_dot(point, axis) for point in endpoints)
            high = max(_dot(point, axis) for point in endpoints)
            coverage = sum(wall["coverage"] for wall in group)
            bins = _common_angular_bins(group, axis)
            states = [wall["end_states"] for wall in group]
            consistent_states = bool(states) and all(state == states[0] for state in states)
            full = (coverage >= 2*math.pi-0.05 and coverage <= 2*math.pi+0.05
                    and bins is not None and len(bins) == 36)
            diagnostics = []
            if not full:
                diagnostics.append("ANGULAR_COVERAGE_INCOMPLETE_OR_UNALIGNED")
            if not consistent_states:
                diagnostics.append("END_MATERIAL_STATES_CONFLICT")
            if not states or len(states[0]) != 2 or states[0] == ["material", "material"]:
                diagnostics.append("OPENING_AND_BOTTOM_UNVERIFIED")
            if any(len(scan.get("material_intervals_mm") or []) > 1
                   for wall in group for scan in wall["end_scan"]):
                diagnostics.append("MULTIPLE_MATERIAL_INTERVALS_NEED_REVIEW")
            if any(scan.get("method") != "exact_centerline_solid_intersection"
                   for wall in group for scan in wall["end_scan"]):
                diagnostics.append("END_INTERVALS_NOT_EXACTLY_VERIFIED")
            status = "confirmed" if not diagnostics else "candidate"
            if status != "confirmed":
                subtype = "cylindrical_void_candidate"
            elif states and states[0] == ["void", "void"]:
                subtype = "through_hole"
            elif states and states[0].count("material") == 1:
                subtype = "blind_hole"
            else:
                subtype = "cylindrical_void_candidate"
            face_group = [wall["face"]["entity_id"] for wall in group]
            tip_faces = []
            bottom_faces = []
            tip_depth = None
            if subtype == "blind_hole" and status == "confirmed":
                entry_scalar = high if states[0] == ["material", "void"] else low
                material_end = low if states[0] == ["material", "void"] else high
                for wall_face_id in face_group:
                    for neighbor_id in graph.face_neighbors(wall_face_id):
                        neighbor = graph.entities.get(neighbor_id, {})
                        if neighbor_id not in face_ids:
                            continue
                        if neighbor.get("geometry_type") == "plane":
                            plane = _plane(neighbor)
                            axis_point = [basis["origin"][i]+axis[i]*(material_end-_dot(basis["origin"], axis)) for i in range(3)]
                            bounds = neighbor.get("bounding_box") or {}
                            if (plane and abs(_dot(plane[0], axis)) > 1-1e-3 and
                                abs(_dot(plane[0], _sub(axis_point, plane[1]))) <= tolerance and
                                all(bounds.get("min", [float("inf")]*3)[i]-tolerance <= axis_point[i] <=
                                    bounds.get("max", [-float("inf")]*3)[i]+tolerance for i in range(3))):
                                bottom_faces.append(neighbor_id)
                            continue
                        if neighbor.get("geometry_type") != "cone":
                            continue
                        apex = (neighbor.get("geometry") or {}).get("apex")
                        if not isinstance(apex, list) or len(apex) != 3:
                            continue
                        apex_line_distance = _line_distance(basis, {"origin": apex})
                        apex_scalar = _dot(apex, axis)
                        if apex_line_distance <= tolerance and ((material_end == low and apex_scalar < low) or
                                                                 (material_end == high and apex_scalar > high)):
                            tip_faces.append(neighbor_id)
                            tip_depth = abs(entry_scalar-apex_scalar)
            payload = {
                "subtype": subtype, "diameter_mm": 2*basis["radius"],
                "cylindrical_wall_length_mm": high-low, "axis_direction": axis,
                "axis_point_mm": basis["origin"], "angular_coverage_rad": coverage,
                "angular_bins_verified": len(bins) if bins is not None else 0,
                "end_states": states[0] if states else [], "wall_face_ids": face_group,
                "end_scan": basis["end_scan"],
                "start_point_mm": min(endpoints, key=lambda point: _dot(point, axis)),
                "end_point_mm": max(endpoints, key=lambda point: _dot(point, axis)),
                "depth_definition": "bounded_cylindrical_wall_axial_length",
                "native_thread_status": "not_evaluated", "classification_status": status,
                "render_range_status": "confirmed" if face_group else "unavailable",
            }
            if tip_faces:
                payload["drill_tip_face_ids"] = sorted(set(tip_faces))
                payload["total_depth_mm"] = tip_depth
                payload["total_depth_definition"] = "entry_plane_to_analytic_cone_apex"
            elif bottom_faces:
                payload["bottom_face_ids"] = sorted(set(bottom_faces))
                payload["flat_bottom_depth_mm"] = high-low
                payload["flat_bottom_depth_definition"] = "entry_to_verified_planar_bottom"
            _record(result, part_id, shape_hash, solid_id, "hole", subtype,
                    {"body_wall": face_group, "drill_tip": sorted(set(tip_faces)),
                     "bottom": sorted(set(bottom_faces))}, payload, status, diagnostics,
                    [("diameter", 2*basis["radius"], "mm", "analytic_cylinder_radius_twice"),
                     ("cylindrical_wall_length", high-low, "mm", "bounded_face_edge_projection")]
                    + ([("total_depth", tip_depth, "mm", "entry_to_cone_apex_projection")] if tip_depth is not None else []), tolerance)
        _combine_step_segments(result, part_id, graph, solid_id, tolerance, shape_hash)
        _recognize_transitions(result, part_id, graph, solid_id, face_ids, tolerance, shape_hash)
        for proposal in planar_structures(graph, solid_id, face_ids, tolerance) + circular_bosses(graph, solid_id, face_ids, tolerance):
            feature = _record(result, part_id, shape_hash, solid_id,
                              proposal["family"], proposal["subtype"], proposal["roles"],
                              proposal["payload"], "confirmed", [], proposal["measures"], tolerance)
            feature.coordinate_frame = proposal["frame"]
        for proposal in structural_proposals(graph, solid_id, face_ids, thin_wall_pairs or [],
                                             result.canonical_features, tolerance):
            feature = _record(result, part_id, shape_hash, solid_id,
                              proposal["family"], proposal["subtype"], proposal["roles"],
                              proposal["payload"], "candidate", proposal["diagnostics"],
                              proposal["measures"], tolerance, measurements_verified=True)
            feature.coordinate_frame = proposal["frame"]
            feature.relations.extend(proposal["relations"])
    return result
