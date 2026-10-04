"""Bounded planar structure proposals from one Solid's existing topology graph.

Only finite shared edges establish membership. The large support plane is
evidence, never part of the default rendered structure extent.
"""

from __future__ import annotations

import math
from typing import Any

from .eaag import EaagGraph


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x*y for x, y in zip(a, b))


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [x-y for x, y in zip(a, b)]


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _oriented_normal(face: dict[str, Any]) -> list[float] | None:
    samples = (face.get("geometry") or {}).get("normal_samples") or []
    try:
        normal = [float(value) for value in samples[0]]
    except (IndexError, TypeError, ValueError):
        return None
    length = _norm(normal)
    return [value/length for value in normal] if length > 1e-8 else None


def _line_points(edge: dict[str, Any]) -> list[list[float]] | None:
    geometry = edge.get("geometry") or {}
    points = [geometry.get("start_point"), geometry.get("end_point")]
    return points if all(isinstance(point, list) and len(point) == 3 for point in points) else None


def _unit(vector: list[float]) -> list[float] | None:
    length = _norm(vector)
    return [value/length for value in vector] if length > 1e-8 else None


def _face_span(graph: EaagGraph, face_id: str, axis: list[float]) -> float | None:
    projections = []
    for edge_id in graph.face_edge_ids(face_id):
        ends = _line_points(graph.entities[edge_id])
        if ends:
            projections.extend(_dot(point, axis) for point in ends)
    return max(projections)-min(projections) if projections else None


def _cap_axes(graph: EaagGraph, cap_id: str, tolerance: float):
    edges = [graph.entities[edge_id] for edge_id in graph.face_edge_ids(cap_id)]
    lines = [(_line_points(edge), edge) for edge in edges if edge.get("geometry_type") == "line"]
    if len(lines) != 4 or any(points is None for points, _ in lines):
        return None
    directions = []
    points = []
    for ends, _ in lines:
        direction = _unit(_sub(ends[1], ends[0]))
        if direction is None:
            return None
        directions.append(direction)
        points.extend(ends)
    first = directions[0]
    second = next((direction for direction in directions[1:] if abs(_dot(first, direction)) < 1e-3), None)
    if second is None or any(max(abs(_dot(direction, first)), abs(_dot(direction, second))) < 1-1e-3
                             for direction in directions):
        return None
    # Stable local axes come from finite edges. Near-square profiles have no
    # geometrically unique long direction, so record that ambiguity.
    spans = []
    for direction in (first, second):
        projected = [_dot(point, direction) for point in points]
        spans.append(max(projected)-min(projected))
    if spans[1] > spans[0] + tolerance:
        first, second = second, first
        spans.reverse()
    return first, second, spans, abs(spans[0]-spans[1]) <= tolerance


def planar_structures(graph: EaagGraph, solid_id: str, face_ids: list[str],
                      tolerance: float) -> list[dict[str, Any]]:
    """Find four straight walls bridging a smaller cap to a larger support."""
    faces = set(face_ids)
    proposals: list[dict[str, Any]] = []
    for cap_id in face_ids:
        cap = graph.entities[cap_id]
        if cap.get("geometry_type") != "plane":
            continue
        cap_normal = _oriented_normal(cap)
        if cap_normal is None:
            continue
        axes = _cap_axes(graph, cap_id, tolerance)
        if axes is None:
            continue
        if abs(float(cap.get("area") or 0)-axes[2][0]*axes[2][1]) > max(tolerance, float(cap.get("area") or 0)*1e-4):
            # A four-edge outer rectangle may still have an inner circular
            # opening; it is not a closed rectangular cap or cavity floor.
            continue
        wall_candidates = []
        for neighbor_id in graph.face_neighbors(cap_id):
            if neighbor_id not in faces:
                continue
            wall = graph.entities[neighbor_id]
            wall_normal = _oriented_normal(wall)
            if wall.get("geometry_type") != "plane" or wall_normal is None or abs(_dot(cap_normal, wall_normal)) > 1e-3:
                continue
            if len([edge_id for edge_id in graph.shared_edge_ids(cap_id, neighbor_id)
                    if graph.entities[edge_id].get("geometry_type") == "line"]) != 1:
                continue
            span = _face_span(graph, neighbor_id, cap_normal)
            if span is not None and span > tolerance:
                wall_candidates.append((neighbor_id, span))
        if len(wall_candidates) != 4:
            continue
        minimum_span = min(span for _, span in wall_candidates)
        walls = [face_id for face_id, span in wall_candidates if abs(span-minimum_span) <= tolerance]
        if len(walls) not in (3, 4):
            continue
        opening_reference = [face_id for face_id, _ in wall_candidates if face_id not in walls]
        common = set(graph.face_neighbors(walls[0]))
        for wall_id in walls[1:]:
            common.intersection_update(graph.face_neighbors(wall_id))
        common.discard(cap_id)
        for support_id in sorted(common):
            if support_id not in faces:
                continue
            support = graph.entities[support_id]
            support_normal = _oriented_normal(support)
            if (support.get("geometry_type") != "plane" or support_normal is None or
                abs(_dot(cap_normal, support_normal)) < 1-1e-3 or
                float(support.get("area") or 0) <= float(cap.get("area") or 0) + tolerance):
                continue
            if any(len([edge_id for edge_id in graph.shared_edge_ids(support_id, wall_id)
                        if graph.entities[edge_id].get("geometry_type") == "line"]) != 1 for wall_id in walls):
                continue
            cap_center, support_center = cap.get("center"), support.get("center")
            if not (isinstance(cap_center, list) and isinstance(support_center, list)):
                continue
            signed_height = _dot(_sub(cap_center, support_center), support_normal)
            if abs(signed_height) <= tolerance:
                continue
            x_axis, y_axis, spans, ambiguous_axes = axes
            if min(spans) <= tolerance:
                continue
            family = "boss" if signed_height > 0 else ("pocket" if len(walls) == 4 else "slot")
            if family == "slot":
                # An open side must lie on the containing Solid's exterior box.
                solid_box = graph.entities[solid_id].get("bounding_box") or {}
                outside_box = graph.entities[opening_reference[0]].get("bounding_box") or {}
                if not any(abs(outside_box.get("min", [float("nan")]*3)[i]-solid_box.get("min", [float("inf")]*3)[i]) <= tolerance or
                           abs(outside_box.get("max", [float("nan")]*3)[i]-solid_box.get("max", [-float("inf")]*3)[i]) <= tolerance
                           for i in range(3)):
                    continue
            height = abs(signed_height)
            parameters = {
                "length_mm": spans[0], "width_mm": spans[1],
                "height_mm" if family == "boss" else "depth_mm": height,
                "dimension_method": "finite_cap_edge_projection_in_local_frame",
                "height_definition": "cap_to_support_plane_along_oriented_support_normal",
                "cap_face_id": cap_id, "wall_face_ids": sorted(walls),
                "support_face_id": support_id, "classification_status": "confirmed",
                "render_range_status": "confirmed", "profile_axis_ambiguous": ambiguous_axes,
            }
            if family == "slot":
                parameters["side_opening_face_ids"] = opening_reference
                parameters["volume_status"] = "not_evaluated_open_boundary"
            elif family == "pocket":
                parameters["bounded_cavity_volume_mm3"] = float(cap["area"])*height
                parameters["volume_method"] = "closed_straight_four_wall_prism_from_cap_and_support"
            proposals.append({
                "family": family, "subtype": "rectangular_straight_wall" if family != "slot" else "open_straight_wall",
                "roles": {"top" if family == "boss" else "cavity_bottom": [cap_id],
                          "side_wall" if family == "boss" else "cavity_wall": sorted(walls),
                          "support": [support_id],
                          "opening_boundary_reference": opening_reference},
                "payload": parameters,
                "frame": {"origin_mm": cap_center, "x_axis": x_axis, "y_axis": y_axis,
                          "normal": support_normal, "axis_selection": "finite_cap_edges"},
                "measures": [("length", spans[0], "mm", "finite_cap_edge_projection"),
                             ("width", spans[1], "mm", "finite_cap_edge_projection"),
                             ("height" if family == "boss" else "depth", height, "mm", "oriented_cap_support_plane_distance")],
            })
            break
    # Open slots can also be viewed from an end wall. Retain the interpretation
    # whose support is the larger exterior host; do not count one void twice.
    return [proposal for proposal in proposals if not any(
        other is not proposal and proposal["family"] == other["family"] == "slot" and
        proposal["payload"]["cap_face_id"] in other["payload"]["wall_face_ids"] and
        float(graph.entities[other["payload"]["support_face_id"]].get("area") or 0) >
        float(graph.entities[proposal["payload"]["support_face_id"]].get("area") or 0)
        for other in proposals)]


def circular_bosses(graph: EaagGraph, solid_id: str, face_ids: list[str],
                    tolerance: float) -> list[dict[str, Any]]:
    """Confirm a full outer cylindrical wall between a disk and host plane."""
    faces = set(face_ids)
    proposals = []
    for wall_id in face_ids:
        wall = graph.entities[wall_id]
        if wall.get("geometry_type") != "cylinder":
            continue
        geometry = wall.get("geometry") or {}
        evidence = geometry.get("recognition_evidence") or {}
        try:
            radius = float(geometry["radius"])
            coverage = float(evidence["angular_coverage_rad"])
            low, high = [float(value) for value in evidence["axial_range_mm"]]
        except (KeyError, TypeError, ValueError):
            continue
        if (evidence.get("status") != "evaluated" or evidence.get("radial_material_side") != "outer_wall" or
            abs(coverage-2*math.pi) > 0.05 or radius <= tolerance or high-low <= tolerance):
            continue
        neighbors = [graph.entities[face_id] for face_id in graph.face_neighbors(wall_id)
                     if face_id in faces and graph.entities[face_id].get("geometry_type") == "plane"]
        if len(neighbors) != 2:
            continue
        cap = next((face for face in neighbors if abs(float(face.get("area") or 0)-math.pi*radius*radius)
                    <= max(tolerance, math.pi*radius*radius*1e-3)), None)
        if cap is None:
            continue
        support = next(face for face in neighbors if face is not cap)
        support_normal = _oriented_normal(support)
        cap_normal = _oriented_normal(cap)
        if support_normal is None or cap_normal is None or abs(_dot(support_normal, cap_normal)) < 1-1e-3:
            continue
        if float(support.get("area") or 0) <= float(cap["area"]) + tolerance:
            continue
        if any(len([edge_id for edge_id in graph.shared_edge_ids(wall_id, face["entity_id"])
                    if graph.entities[edge_id].get("geometry_type") == "circle"]) != 1
               for face in (cap, support)):
            continue
        signed = _dot(_sub(cap["center"], support["center"]), support_normal)
        if abs(signed-(high-low)) > tolerance:
            continue
        axis = _unit([float(value) for value in evidence["axis_unit"]])
        if axis is None:
            continue
        base = [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0]
        x_axis = _unit([axis[1]*base[2]-axis[2]*base[1], axis[2]*base[0]-axis[0]*base[2],
                        axis[0]*base[1]-axis[1]*base[0]])
        y_axis = [axis[1]*x_axis[2]-axis[2]*x_axis[1], axis[2]*x_axis[0]-axis[0]*x_axis[2],
                  axis[0]*x_axis[1]-axis[1]*x_axis[0]]
        proposals.append({
            "family": "boss", "subtype": "circular_straight_wall",
            "roles": {"boss_top": [cap["entity_id"]], "boss_wall": [wall_id],
                      "support": [support["entity_id"]]},
            "payload": {"diameter_mm": 2*radius, "height_mm": signed,
                        "dimension_method": "analytic_cylinder_and_bounded_cap_support_planes",
                        "cap_face_id": cap["entity_id"], "wall_face_ids": [wall_id],
                        "support_face_id": support["entity_id"],
                        "classification_status": "confirmed", "render_range_status": "confirmed"},
            "frame": {"origin_mm": cap["center"], "x_axis": x_axis, "y_axis": y_axis,
                      "normal": support_normal, "axis_selection": "analytic_cylinder_axis"},
            "measures": [("diameter", 2*radius, "mm", "analytic_cylinder_radius_twice"),
                         ("height", signed, "mm", "bounded_cap_support_plane_distance")],
        })
    return proposals
