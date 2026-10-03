"""Exact B-Rep queries run only in the isolated FreeCAD interpreter.

Input paths are prepared by the backend from a published geometry snapshot. This
script never accepts an HTTP supplied path or evaluates user expressions.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import FreeCAD
import Part


def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def vector(values):
    return FreeCAD.Vector(*[float(value) for value in values])


def shape_at(path, kind):
    shape = Part.Shape()
    shape.read(str(path))
    if shape.isNull():
        raise ValueError("geometry_unavailable: empty B-Rep")
    groups = {"face": shape.Faces, "edge": shape.Edges, "vertex": shape.Vertexes,
              "solid": shape.Solids}
    selected = groups.get(kind)
    if not selected or len(selected) != 1:
        raise ValueError("stale_reference: B-Rep topology kind differs")
    return selected[0]


def finite_point(values):
    if not isinstance(values, list) or len(values) != 3 or not all(math.isfinite(float(x)) for x in values):
        raise ValueError("invalid_input: point must be finite XYZ")
    return vector(values)


def bbox(shape):
    b = shape.BoundBox
    return {"min": [b.XMin, b.YMin, b.ZMin], "max": [b.XMax, b.YMax, b.ZMax]}


def face_normal(face, location):
    point = finite_point(location)
    if face.distToShape(Part.Vertex(point))[0] > 1.0e-5:
        raise ValueError("invalid_input: point is not on selected face")
    u, v = face.Surface.parameter(point)
    normal = face.normalAt(u, v)
    if normal.Length <= 1.0e-12:
        raise ValueError("unsupported: zero surface normal")
    normal.normalize()
    return normal


def detail(shape, params):
    kind = shape.ShapeType.lower()
    result = {"kind": kind, "bounding_box": bbox(shape)}
    if hasattr(shape, "CenterOfMass"):
        result["center_of_mass"] = xyz(shape.CenterOfMass)
    if kind == "vertex":
        result["point"] = xyz(shape.Point)
    elif kind == "edge":
        result.update(length_mm=float(shape.Length), curve_type=type(shape.Curve).__name__,
                      endpoints=[xyz(v.Point) for v in shape.Vertexes])
        curve = shape.Curve
        if hasattr(curve, "Radius"):
            result["radius_mm"] = float(curve.Radius)
        if hasattr(curve, "Center"):
            result["circle_center"] = xyz(curve.Center)
        result["parameter_range"] = [float(shape.FirstParameter), float(shape.LastParameter)]
    elif kind == "face":
        result.update(area_mm2=float(shape.Area), perimeter_mm=float(sum(e.Length for e in shape.Edges)),
                      surface_type=type(shape.Surface).__name__,
                      boundary_count=len(shape.Wires), edge_count=len(shape.Edges),
                      parameter_range=[float(x) for x in shape.ParameterRange])
        surface = shape.Surface
        if hasattr(surface, "Radius"):
            result["radius_mm"] = float(surface.Radius)
        if hasattr(surface, "Center"):
            result["surface_center"] = xyz(surface.Center)
        if params.get("point") is not None:
            result["normal_at_point"] = xyz(face_normal(shape, params["point"]))
    elif kind == "solid":
        result.update(volume_mm3=float(shape.Volume), surface_area_mm2=float(shape.Area),
                      face_count=len(shape.Faces), edge_count=len(shape.Edges))
    else:
        raise ValueError("unsupported: detail type")
    return {"status": "success", "values": result, "unit": "mm"}


def distance(a, b, tolerance):
    value, point_pairs, _ = a.distToShape(b)
    if not point_pairs:
        return {"status": "empty", "values": None, "diagnostic": "no nearest points"}
    pairs = [{"a": xyz(left), "b": xyz(right)} for left, right in point_pairs[:16]]
    return {"status": "multiple" if len(point_pairs) > 1 else "success",
            "values": {"distance_mm": float(value), "nearest_points": pairs,
                       "intersects": bool(value <= tolerance), "solution_count": len(point_pairs)},
            "unit": "mm"}


def direction(shape, location):
    kind = shape.ShapeType.lower()
    if kind == "edge":
        if type(shape.Curve).__name__ != "Line":
            if location is None:
                raise ValueError("invalid_input: curve tangent needs a point")
            point = finite_point(location)
            param = shape.Curve.parameter(point)
            tangent = shape.tangentAt(param)
        else:
            if len(shape.Vertexes) < 2:
                raise ValueError("unsupported: edge has no endpoints")
            tangent = shape.Vertexes[-1].Point - shape.Vertexes[0].Point
        if tangent.Length <= 1.0e-12:
            raise ValueError("unsupported: zero tangent")
        tangent.normalize()
        return tangent, "line"
    if kind == "face":
        if location is None:
            if type(shape.Surface).__name__ != "Plane":
                raise ValueError("invalid_input: curved face needs a point")
            u0, u1, v0, v1 = shape.ParameterRange
            normal = shape.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            normal.normalize()
            return normal, "plane"
        return face_normal(shape, location), "plane"
    raise ValueError("unsupported: angle object type")


def angle(a, b, params):
    left, left_kind = direction(a, params.get("point_a"))
    right, right_kind = direction(b, params.get("point_b"))
    cosine = max(-1.0, min(1.0, left.dot(right)))
    if params.get("orientation") == "unoriented":
        cosine = abs(cosine)
    elif params.get("orientation") != "directed":
        raise ValueError("invalid_input: orientation must be directed or unoriented")
    degrees = math.degrees(math.acos(cosine))
    if left_kind != right_kind:
        if params["orientation"] == "directed":
            raise ValueError("unsupported: directed line-plane angle needs a reference normal")
        degrees = 90.0 - degrees if params["orientation"] == "unoriented" else abs(90.0 - degrees)
    return {"status": "success", "values": {"angle_deg": degrees,
            "definition": f"{left_kind}_{right_kind}", "orientation": params["orientation"],
            "direction_a": xyz(left), "direction_b": xyz(right)}, "unit": "deg"}


def section(solid, params):
    if solid.ShapeType != "Solid":
        raise ValueError("unsupported: section requires closed solid")
    origin = finite_point(params.get("origin"))
    normal = finite_point(params.get("normal"))
    if normal.Length <= 1.0e-12:
        raise ValueError("invalid_input: zero section normal")
    normal.normalize()
    span = max(1.0, solid.BoundBox.DiagonalLength * 4.0)
    plane = Part.makePlane(span, span, origin, normal)
    plane.translate(origin - plane.CenterOfMass)
    common = solid.common(plane)
    if common.isNull():
        return {"status": "empty", "values": {"regions": [], "curves": []}, "unit": "mm"}
    regions = [{"area_mm2": float(face.Area), "boundary_count": len(face.Wires),
                "perimeter_mm": float(sum(edge.Length for edge in face.Edges))} for face in common.Faces]
    curves = [{"length_mm": float(edge.Length), "endpoints": [xyz(v.Point) for v in edge.Vertexes],
               "display_points": [xyz(point) for point in edge.discretize(Deflection=0.1)[:1000]]}
              for edge in common.Edges]
    return {"status": "success" if regions else "multiple", "values": {
        "regions": regions, "net_area_mm2": sum(item["area_mm2"] for item in regions),
        "curves": curves, "region_count": len(regions), "display_deflection_mm": 0.1}, "unit": "mm"}


def local_thickness(face, solid, params, tolerance):
    if face.ShapeType != "Face" or solid.ShapeType != "Solid" or not solid.isClosed():
        raise ValueError("unsupported: thickness requires face and closed solid")
    point = finite_point(params.get("point"))
    normal = face_normal(face, params["point"])
    epsilon = max(tolerance * 2.0, solid.BoundBox.DiagonalLength * 1.0e-7)
    inside_plus = solid.isInside(point + normal * epsilon, tolerance, False)
    inside_minus = solid.isInside(point - normal * epsilon, tolerance, False)
    if inside_plus == inside_minus:
        raise ValueError("unsupported: material side ambiguous")
    inward = normal if inside_plus else -normal
    span = max(1.0, solid.BoundBox.DiagonalLength * 2.0)
    ray = Part.makeLine(point + inward * epsilon, point + inward * span)
    segment_shape = solid.common(ray)
    candidates = []
    for edge in segment_shape.Edges:
        ends = [vertex.Point for vertex in edge.Vertexes]
        if len(ends) != 2:
            continue
        projections = sorted((end - point).dot(inward) for end in ends)
        if projections[0] <= epsilon + tolerance * 3 and projections[1] > projections[0] + tolerance:
            candidates.append(projections[1])
    if len(candidates) != 1:
        raise ValueError("unsupported: continuous material interval ambiguous")
    thickness = candidates[0]
    end = point + inward * thickness
    return {"status": "success", "values": {"local_normal_thickness_mm": thickness,
            "start": xyz(point), "end": xyz(end), "direction": xyz(inward),
            "material_intervals": [[0.0, thickness]], "sample_count": 1}, "unit": "mm"}


def run(job):
    start = time.perf_counter()
    shapes = [shape_at(path, kind) for path, kind in zip(job["asset_paths"], job["asset_kinds"])]
    load_ms = (time.perf_counter() - start) * 1000.0
    params = job.get("parameters") or {}
    tolerance = float(job.get("tolerance_mm", 0.01))
    operation = job["operation"]
    started = time.perf_counter()
    if operation == "detail":
        result = detail(shapes[0], params)
    elif operation == "distance":
        result = distance(shapes[0], shapes[1], tolerance)
    elif operation == "angle":
        result = angle(shapes[0], shapes[1], params)
    elif operation == "section":
        result = section(shapes[0], params)
    elif operation == "local_thickness":
        result = local_thickness(shapes[0], shapes[1], params, tolerance)
    else:
        raise ValueError("unsupported: operation")
    result["diagnostics"] = {"load_ms": round(load_ms, 3),
                             "query_ms": round((time.perf_counter() - started) * 1000.0, 3),
                             "loaded_shapes": len(shapes), "cache_hit": False}
    result["kernel"] = "FreeCAD/OpenCascade"
    result["kernel_version"] = ".".join(str(value) for value in FreeCAD.Version()[:3])
    return result


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(job)
    except ValueError as exc:
        message = str(exc)
        prefix, _, description = message.partition(":")
        result = {"status": prefix if prefix in {"invalid_input", "unsupported", "geometry_unavailable", "stale_reference"} else "failed",
                  "values": None, "diagnostic": description.strip() or message}
    except Exception as exc:
        result = {"status": "failed", "values": None, "diagnostic": type(exc).__name__ + ": " + str(exc)}
    Path(job["result_json_path"]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
