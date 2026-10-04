"""Bounded world-placed STEP object relations in one isolated FreeCAD process."""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import FreeCAD
import Part

from measure_geometry import GeometryKernelContext, xyz


MAX_SOLIDS = 64
MAX_PAIRS = 128


def box_distance(left, right):
    a, b = left.BoundBox, right.BoundBox
    gaps = [max(0.0, other_lower - upper, lower - other_upper)
            for lower, upper, other_lower, other_upper in (
                (a.XMin, a.XMax, b.XMin, b.XMax),
                (a.YMin, a.YMax, b.YMin, b.YMax),
                (a.ZMin, a.ZMax, b.ZMin, b.ZMax))]
    return math.sqrt(sum(gap * gap for gap in gaps))


def coplanar_contact_area(left, right, tolerance):
    area = 0.0
    regions = 0
    for face_a in left.Faces:
        if type(face_a.Surface).__name__ != "Plane":
            continue
        u0, u1, v0, v1 = face_a.ParameterRange
        normal_a = face_a.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        for face_b in right.Faces:
            if type(face_b.Surface).__name__ != "Plane":
                continue
            p0, p1, q0, q1 = face_b.ParameterRange
            normal_b = face_b.normalAt((p0 + p1) / 2, (q0 + q1) / 2)
            if abs(normal_a.dot(normal_b)) < 0.999999:
                continue
            if abs((face_b.CenterOfMass - face_a.CenterOfMass).dot(normal_a)) > tolerance:
                continue
            overlap = face_a.common(face_b)
            local_area = float(sum(face.Area for face in overlap.Faces))
            if local_area <= tolerance * tolerance:
                # OCC can return an empty face common for coincident trimmed
                # planes. Only accept a bounded convex tri/quad entirely on
                # the other trimmed face; do not approximate partial overlap.
                for smaller, larger in sorted(((face_a, face_b), (face_b, face_a)),
                                              key=lambda pair: pair[0].Area):
                    if len(smaller.Wires) != 1 or len(larger.Wires) != 1 or len(smaller.Vertexes) not in (3, 4):
                        continue
                    samples = [vertex.Point for vertex in smaller.Vertexes]
                    samples.extend(edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2)
                                   for edge in smaller.Edges)
                    if all(larger.distToShape(Part.Vertex(point))[0] <= tolerance for point in samples):
                        local_area = float(smaller.Area)
                        break
            if local_area <= tolerance * tolerance:
                # Exact rectangle intersection for the deliberately narrow
                # axis-aligned planar subclass (e.g. orthogonal plate faces).
                axis = max(range(3), key=lambda index: abs((normal_a.x, normal_a.y, normal_a.z)[index]))
                coordinates = ("X", "Y", "Z")
                if (abs((normal_a.x, normal_a.y, normal_a.z)[axis]) > 0.999999 and
                    len(face_a.Wires) == len(face_b.Wires) == 1 and
                    len(face_a.Vertexes) == len(face_b.Vertexes) == 4):
                    side_axes = [index for index in range(3) if index != axis]
                    bounds = []
                    valid = True
                    for face in (face_a, face_b):
                        box = face.BoundBox
                        ranges = [(getattr(box, coordinates[k] + "Min"),
                                   getattr(box, coordinates[k] + "Max")) for k in side_axes]
                        expected_area = (ranges[0][1] - ranges[0][0]) * (ranges[1][1] - ranges[1][0])
                        if abs(face.Area - expected_area) > max(tolerance * tolerance, expected_area * 1e-8):
                            valid = False
                        bounds.append(ranges)
                    if valid:
                        spans = [max(0.0, min(bounds[0][k][1], bounds[1][k][1]) -
                                     max(bounds[0][k][0], bounds[1][k][0])) for k in range(2)]
                        local_area = spans[0] * spans[1]
            if local_area > tolerance * tolerance:
                area += local_area
                regions += 1
    return area, regions


def verified_box_contact_area(left, right, tolerance):
    def box_dimensions(shape):
        box = shape.BoundBox
        dimensions = [box.XLength, box.YLength, box.ZLength]
        if (len(shape.Faces) != 6 or any(type(face.Surface).__name__ != "Plane" for face in shape.Faces)
            or any(length <= tolerance for length in dimensions)):
            return None
        expected_volume = dimensions[0] * dimensions[1] * dimensions[2]
        expected_area = 2 * sum(dimensions[i] * dimensions[(i + 1) % 3] for i in range(3))
        if abs(shape.Volume - expected_volume) > max(tolerance ** 3, expected_volume * 1e-8):
            return None
        if abs(shape.Area - expected_area) > max(tolerance ** 2, expected_area * 1e-8):
            return None
        return [(box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax)]

    a, b = box_dimensions(left), box_dimensions(right)
    if a is None or b is None:
        return 0.0
    touching_axes = [i for i in range(3) if abs(a[i][1] - b[i][0]) <= tolerance or
                     abs(b[i][1] - a[i][0]) <= tolerance]
    if len(touching_axes) != 1:
        return 0.0
    other_axes = [i for i in range(3) if i != touching_axes[0]]
    spans = [max(0.0, min(a[i][1], b[i][1]) - max(a[i][0], b[i][0])) for i in other_axes]
    return spans[0] * spans[1]


def orthogonal_plate_overlap(left, right, tolerance, minimum_fraction):
    """Customer lap rule, only for two validated axis-aligned rectangular plates."""
    def bounds(shape):
        box = shape.BoundBox
        spans = [box.XLength, box.YLength, box.ZLength]
        if (len(shape.Faces) != 6 or not shape.isClosed() or
                any(type(face.Surface).__name__ != "Plane" for face in shape.Faces) or
                any(span <= tolerance for span in spans)):
            return None
        if abs(shape.Volume - spans[0] * spans[1] * spans[2]) > max(tolerance ** 3, shape.Volume * 1e-8):
            return None
        return [(box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax)]

    a, b = bounds(left), bounds(right)
    if a is None or b is None:
        return None
    axes = [i for i in range(3) if abs(a[i][1] - b[i][0]) <= tolerance or
            abs(b[i][1] - a[i][0]) <= tolerance]
    if len(axes) != 1:
        return None
    axis = axes[0]
    side = [i for i in range(3) if i != axis]
    sizes_a = [a[i][1] - a[i][0] for i in range(3)]
    sizes_b = [b[i][1] - b[i][0] for i in range(3)]
    if any(sizes[axis] >= min(sizes[i] for i in side) for sizes in (sizes_a, sizes_b)):
        return None
    overlap = [max(0, min(a[i][1], b[i][1]) - max(a[i][0], b[i][0])) for i in side]
    actual = overlap[0] * overlap[1]
    smaller_face = min(sizes_a[side[0]] * sizes_a[side[1]],
                       sizes_b[side[0]] * sizes_b[side[1]])
    fraction = actual / smaller_face
    return {"subclass": "orthogonal_plate_face_overlap", "joint_kind": "lap",
            "status": "confirmed" if actual > tolerance * tolerance and fraction >= minimum_fraction else "candidate",
            "contact_area_mm2": actual, "denominator": "smaller_finite_plate_face",
            "denominator_area_mm2": smaller_face, "overlap_fraction": fraction,
            "contact_normal_axis": "XYZ"[axis], "opposed_normals": True,
            "minimum_fraction": minimum_fraction, "rule_version": "customer.lap.orthogonal_plate.v1"}


def evaluate_pair(left, right, tolerance, minimum_lap_fraction=0.5):
    distance, witnesses, _ = left.distToShape(right)
    if not math.isfinite(distance) or not witnesses:
        return {"status": "failed", "diagnostic": "finite shortest distance unavailable"}
    result = {"status": "evaluated", "distance_mm": float(distance),
              "within_tolerance": bool(distance <= tolerance),
              "witnesses": [{"a": xyz(a), "b": xyz(b)} for a, b in witnesses[:16]],
              "solution_count": len(witnesses), "contact_kind": "separated",
              "intersection_status": "not_evaluated", "interference_volume_mm3": None,
              "actual_contact_area_mm2": None}
    if distance > 0:
        result["intersection_status"] = "empty"
        result["contact_kind"] = "positive_gap"
        return result
    if not left.isClosed() or not right.isClosed() or not left.isValid() or not right.isValid():
        result["intersection_status"] = "invalid_or_open_solid"
        return result
    try:
        contact_area, region_count = coplanar_contact_area(left, right, tolerance)
        if contact_area <= tolerance * tolerance:
            contact_area = verified_box_contact_area(left, right, tolerance)
            region_count = 1 if contact_area > 0 else 0
        overlap = left.common(right)
        if overlap.isNull():
            result["intersection_status"] = "zero_volume" if contact_area > 0 else "indeterminate_zero_distance"
            result["contact_kind"] = "face_contact" if contact_area > 0 else "indeterminate_zero_distance"
            if contact_area > 0:
                result["actual_contact_area_mm2"] = contact_area
                result["contact_region_count"] = region_count
                result["joint_classification"] = orthogonal_plate_overlap(left, right, tolerance,
                                                                             minimum_lap_fraction)
            return result
        volume = float(overlap.Volume)
        result["interference_volume_mm3"] = volume
        if volume > max(1e-12, tolerance ** 3):
            result["intersection_status"] = "positive_volume"
            result["contact_kind"] = "interference"
        elif volume > 0:
            result["intersection_status"] = "numerically_uncertain_volume"
            result["contact_kind"] = "uncertain"
        else:
            result["intersection_status"] = "zero_volume"
            area = float(sum(face.Area for face in overlap.Faces))
            if max(area, contact_area) > tolerance * tolerance:
                result["contact_kind"] = "face_contact"
                result["actual_contact_area_mm2"] = contact_area if contact_area > 0 else area
                result["contact_region_count"] = region_count if contact_area > 0 else len(overlap.Faces)
                result["joint_classification"] = orthogonal_plate_overlap(left, right, tolerance,
                                                                             minimum_lap_fraction)
            elif any(edge.Length > tolerance for edge in overlap.Edges):
                result["contact_kind"] = "line_contact"
            elif overlap.Vertexes:
                result["contact_kind"] = "point_contact"
            else:
                result["contact_kind"] = "indeterminate_zero_distance"
    except Exception as exc:
        result["intersection_status"] = "boolean_failed"
        result["contact_kind"] = "unknown"
        result["diagnostic"] = type(exc).__name__
    return result


def run(job):
    items = job.get("instances") or []
    tolerance = float(job.get("tolerance_mm", 0.01))
    radius = float(job.get("candidate_distance_mm", 10.0))
    minimum_lap_fraction = float(job.get("minimum_lap_fraction", 0.5))
    if not 1 <= len(items) <= MAX_SOLIDS or not math.isfinite(tolerance) or tolerance <= 0 or not math.isfinite(radius) or radius < 0 or not math.isfinite(minimum_lap_fraction) or not 0 < minimum_lap_fraction <= 1:
        raise ValueError("invalid_input: solid count or tolerance")
    if any(item.get("coordinate_convention") != "world_placed_step" or
           not item.get("instance_id") or not item.get("solid_id") for item in items):
        raise ValueError("unsupported: trusted world-placed STEP instance mapping required")
    context = GeometryKernelContext([item["asset_path"] for item in items], ["solid"] * len(items), tolerance)
    if any(len(shape.Faces) > 256 for shape in context.shapes):
        raise ValueError("invalid_input: solid face count exceeds 256 per task")
    started = time.perf_counter()
    records = []
    excluded = 0
    for i, left in enumerate(items):
        for j in range(i + 1, len(items)):
            right = items[j]
            if left["instance_id"] == right["instance_id"]:
                continue
            if box_distance(context.shapes[i], context.shapes[j]) > radius:
                excluded += 1
                continue
            if len(records) >= MAX_PAIRS:
                raise ValueError("invalid_input: candidate pair limit exceeded; narrow analysis scope")
            relation = evaluate_pair(context.shapes[i], context.shapes[j], tolerance, minimum_lap_fraction)
            records.append({"instance_a": left["instance_id"], "instance_b": right["instance_id"],
                            "solid_a": left["solid_id"], "solid_b": right["solid_id"], **relation})
    return {"status": "success", "relations": records, "excluded_pair_count": excluded,
            "evaluated_pair_count": len(records), "coordinate_system": "step_world",
            "source": "auxiliary_brep", "algorithm_version": "assembly.p6a.v1",
            "diagnostics": {"load_ms": round(context.load_ms, 3),
                            "compute_ms": round((time.perf_counter() - started) * 1000, 3),
                            "loaded_shapes": context.loaded_shapes, "pair_count": len(records)},
            "kernel": "OpenCascade", "kernel_version": str(getattr(Part, "OCC_VERSION", "unknown") or "unknown"),
            "freecad_version": ".".join(str(value) for value in FreeCAD.Version()[:3])}


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(job)
    except ValueError as exc:
        code, _, message = str(exc).partition(":")
        result = {"status": code if code in {"invalid_input", "unsupported"} else "failed",
                  "diagnostic": message.strip() or str(exc)}
    except Exception as exc:
        result = {"status": "failed", "diagnostic": type(exc).__name__ + ": " + str(exc)}
    Path(job["result_json_path"]).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
