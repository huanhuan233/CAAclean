"""Bounded exact straight hollow tube recognition from one loaded B-Rep task.

The narrow positive class needs both concentric full cylindrical walls, two
annular planar ends and the matching material volume. Other solids remain
unsupported; this script never infers a CATIA feature or manufacturing method.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import FreeCAD
import Part

from measure_geometry import GeometryKernelContext, xyz
from assembly_relations import evaluate_pair


MAX_SOLIDS = 32
MAX_FACES = 256


def _point_on_axis(point, origin, axis):
    return origin + axis * ((point - origin).dot(axis))


def _axial_interval(face, origin, axis):
    values = [(vertex.Point - origin).dot(axis) for vertex in face.Vertexes]
    return (min(values), max(values)) if values else None


def _classify_straight_tube(solid, tolerance):
    base = {"status": "unsupported_geometry", "source": "derived_geometry",
            "unmet_conditions": ["bounded_concentric_hollow_straight_tube_not_proved"]}
    if solid.ShapeType != "Solid" or not solid.isValid() or not solid.isClosed() or len(solid.Faces) != 4:
        return base
    cylinders = [face for face in solid.Faces if type(face.Surface).__name__ == "Cylinder"]
    planes = [face for face in solid.Faces if type(face.Surface).__name__ == "Plane"]
    if len(cylinders) != 2 or len(planes) != 2:
        return base
    outer, inner = sorted(cylinders, key=lambda face: float(face.Surface.Radius), reverse=True)
    ro, ri = float(outer.Surface.Radius), float(inner.Surface.Radius)
    if ri <= tolerance or ro - ri <= tolerance:
        return base
    origin, axis = outer.Surface.Center, outer.Surface.Axis
    axis.normalize()
    other_axis = inner.Surface.Axis
    other_axis.normalize()
    axis_offset = (inner.Surface.Center - _point_on_axis(inner.Surface.Center, origin, axis)).Length
    if abs(axis.dot(other_axis)) < 1 - 1e-8 or axis_offset > tolerance:
        return base
    intervals = [_axial_interval(face, origin, axis) for face in (outer, inner)]
    if any(interval is None for interval in intervals):
        return base
    low, high = intervals[0]
    length = high - low
    if length <= tolerance or any(abs(a - b) > tolerance for a, b in zip(intervals[0], intervals[1])):
        return base
    for face in cylinders:
        u0, u1, _, _ = face.ParameterRange
        if abs(abs(u1 - u0) - 2 * math.pi) > 1e-5:
            return base
        if len(face.Wires) != 1:
            return base
    expected_area = math.pi * (ro * ro - ri * ri)
    if abs(solid.Volume - expected_area * length) > max(tolerance ** 3, expected_area * length * 1e-6):
        return base
    ends = []
    for face in planes:
        u0, u1, v0, v1 = face.ParameterRange
        normal = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        if abs(normal.dot(axis)) < 1 - 1e-8 or len(face.Wires) != 2:
            return base
        if abs(float(face.Area) - expected_area) > max(tolerance ** 2, expected_area * 1e-6):
            return base
        if any(type(edge.Curve).__name__ != "Circle" for edge in face.Edges):
            return base
        if len(face.Edges) != 2:
            return base
        edge_radii = sorted(float(edge.Curve.Radius) for edge in face.Edges)
        if abs(edge_radii[0] - ri) > tolerance or abs(edge_radii[1] - ro) > tolerance:
            return base
        station = (face.CenterOfMass - origin).dot(axis)
        if min(abs(station - low), abs(station - high)) > tolerance:
            return base
        ends.append({"kind": "flat", "position_mm": xyz(_point_on_axis(face.CenterOfMass, origin, axis)),
                     "plane_normal": xyz(normal), "boundary_radii_mm": edge_radii,
                     "evidence": "analytic_annular_planar_face"})
    if abs(ends[0]["plane_normal"][0] * ends[1]["plane_normal"][0] +
           ends[0]["plane_normal"][1] * ends[1]["plane_normal"][1] +
           ends[0]["plane_normal"][2] * ends[1]["plane_normal"][2] + 1) > 1e-8:
        return base
    start, finish = origin + axis * low, origin + axis * high
    if tuple(xyz(finish)) < tuple(xyz(start)):
        start, finish = finish, start
        axis = axis * -1
        ends.reverse()
    middle = (start + finish) * 0.5
    return {"status": "confirmed_straight_hollow_tube", "source": "derived_geometry",
            "path": {"kind": "straight", "start_mm": xyz(start), "end_mm": xyz(finish),
                     "direction": xyz(axis), "length_mm": length,
                     "coordinate_system": "solid_definition", "method": "concentric_cylindrical_walls"},
            "section": {"status": "analytic_concentric_annulus", "station_s_mm": length / 2,
                        "origin_mm": xyz(middle), "normal": xyz(axis),
                        "outer_diameter_mm": 2 * ro, "inner_diameter_mm": 2 * ri,
                        "wall_thickness_mm": ro - ri,
                        "material_area_mm2": expected_area,
                        "method": "two_full_cylinders_and_annular_end_faces",
                        "scope": "validated_straight_solid"},
            "ends": ends, "unmet_conditions": []}


def run(job):
    items = job.get("solids") or []
    tolerance = float(job.get("tolerance_mm", 0.01))
    if not 1 <= len(items) <= MAX_SOLIDS or not math.isfinite(tolerance) or not 0 < tolerance <= 0.1:
        raise ValueError("invalid_input: solid count or tolerance")
    if any(not item.get("solid_id") or not item.get("asset_path") for item in items):
        raise ValueError("invalid_input: solid identity and asset required")
    context = GeometryKernelContext([item["asset_path"] for item in items], ["solid"] * len(items), tolerance)
    started = time.perf_counter()
    records = []
    for item, solid in zip(items, context.shapes):
        if len(solid.Faces) > MAX_FACES:
            records.append({"solid_id": item["solid_id"], "status": "analysis_budget_exceeded",
                            "source": "derived_geometry", "unmet_conditions": ["face_count_over_256"]})
        else:
            records.append({"solid_id": item["solid_id"], **_classify_straight_tube(solid, tolerance)})
    clearances = []
    target_id = job.get("target_tube_solid_id")
    if target_id is not None:
        matches = [index for index, item in enumerate(items) if item["solid_id"] == target_id]
        if len(matches) != 1 or records[matches[0]]["status"] != "confirmed_straight_hollow_tube":
            raise ValueError("unsupported: target is not one verified straight hollow tube")
        target_index = matches[0]
        tube = context.shapes[target_index]
        outer = max((face for face in tube.Faces if type(face.Surface).__name__ == "Cylinder"),
                    key=lambda face: face.Surface.Radius)
        # The inner cylindrical wall is intentionally excluded from the
        # installation exterior. The two annular end faces remain included.
        exterior = Part.makeCompound([outer, *(face for face in tube.Faces if type(face.Surface).__name__ == "Plane")])
        path = records[target_index]["path"]
        start = FreeCAD.Vector(*path["start_mm"])
        direction = FreeCAD.Vector(*path["direction"])
        for index, item in enumerate(items):
            if index == target_index:
                continue
            neighbor = context.shapes[index]
            pair = evaluate_pair(tube, neighbor, tolerance)
            try:
                distance, witnesses, _ = exterior.distToShape(neighbor)
                if not math.isfinite(distance) or not witnesses:
                    raise ValueError("finite exterior witness unavailable")
                actual = [{"tube": xyz(a), "target": xyz(b),
                           "s_mm": max(0.0, min(path["length_mm"], (a - start).dot(direction)))}
                          for a, b in witnesses[:16]]
                status = "evaluated" if pair.get("status") == "evaluated" else "partial"
                if distance > tolerance and pair.get("distance_mm", 0) <= tolerance:
                    status = "partial"
                clearances.append({"tube_solid_id": target_id, "target_solid_id": item["solid_id"],
                                   "status": status, "distance_mm": float(distance),
                                   "within_tolerance": bool(distance <= tolerance),
                                   "witnesses": actual, "solution_count": len(witnesses),
                                   "intersection_status": pair.get("intersection_status", "not_evaluated"),
                                   "contact_kind": pair.get("contact_kind", "unknown"),
                                   "method": "exact_exterior_faces_to_target_solid",
                                   "scope": "full_outer_cylindrical_wall_and_two_annular_ends",
                                   "threshold_status": "not_provided"})
            except Exception as exc:
                clearances.append({"tube_solid_id": target_id, "target_solid_id": item["solid_id"],
                                   "status": "failed", "diagnostic": type(exc).__name__,
                                   "distance_mm": None, "intersection_status": pair.get("intersection_status", "not_evaluated")})
    return {"status": "success", "records": records, "clearances": clearances,
            "algorithm_version": "tube.geometry.p7c.v1" if target_id is not None else "tube.geometry.p7b.v1",
            "diagnostics": {"loaded_shapes": context.loaded_shapes, "load_ms": context.load_ms,
                            "compute_ms": round((time.perf_counter() - started) * 1000, 3)},
            "kernel": "OpenCascade", "kernel_version": str(getattr(Part, "OCC_VERSION", "unknown") or "unknown"),
            "freecad_version": ".".join(str(value) for value in FreeCAD.Version()[:3])}


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(job)
    except ValueError as exc:
        result = {"status": "invalid_input", "diagnostic": str(exc)}
    except Exception as exc:
        result = {"status": "failed", "diagnostic": type(exc).__name__ + ": " + str(exc)}
    Path(job["result_json_path"]).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
