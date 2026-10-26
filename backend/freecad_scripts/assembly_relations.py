# 装配空间关系核验：对可信世界坐标实体做距离、接触和干涉计算。
# 包围盒只用于候选剔除；搭接/对接分类限定于经过尺寸和拓扑核验的矩形板子类。

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


# 计算轴对齐包围盒间的距离下界，用于快速排除远处对象，不作为最终表面间隙。
def box_distance(left, right):
    a, b = left.BoundBox, right.BoundBox
    gaps = [max(0.0, other_lower - upper, lower - other_upper)
            for lower, upper, other_lower, other_upper in (
                (a.XMin, a.XMax, b.XMin, b.XMax),
                (a.YMin, a.YMax, b.YMin, b.YMax),
                (a.ZMin, a.ZMax, b.ZMin, b.ZMax))]
    return math.sqrt(sum(gap * gap for gap in gaps))


# 只累计相向外法向的共面裁剪面重叠；矩形回退先校验面积，避免把任意包围盒当接触面。
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
            # A physical face contact needs opposed outward normals. Parallel
            # coplanar faces with the same material side are not a joint.
            if normal_a.dot(normal_b) > -0.999999:
                continue
            if abs((face_b.CenterOfMass - face_a.CenterOfMass).dot(normal_a)) > tolerance:
                continue
            overlap = face_a.common(face_b)
            local_area = float(sum(face.Area for face in overlap.Faces))
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


# 对六个平面、体积和面积均符合轴对齐长方体的对象，计算唯一接触轴上的重叠面积。
def verified_box_contact_area(left, right, tolerance):
    # 验证实体确实符合长方体条件，失败返回 None，阻止包围盒捷径用于一般几何。
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


# 按较小有限板面面积定义搭接比例；只有窄子类条件和比例阈值满足时才确认搭接几何。
def orthogonal_plate_overlap(left, right, tolerance, minimum_fraction):
    """Customer lap rule, only for two validated axis-aligned rectangular plates."""
    # 验证闭合六面体及其包围盒体积一致性，返回三个坐标区间供矩形板规则使用。
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


# 核验同厚度方向、同厚度区间的板端接触；几何对接确认后，功能角色仍保留 needs_review。
def orthogonal_plate_butt(left, right, tolerance):
    """Confirmed coplanar end-face contact for a narrow rectangular plate subclass."""
    boxes = [shape.BoundBox for shape in (left, right)]
    bounds = [[(box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax)] for box in boxes]
    dimensions = [[upper - lower for lower, upper in item] for item in bounds]
    for shape, sizes in zip((left, right), dimensions):
        if (len(shape.Faces) != 6 or not shape.isClosed() or not shape.isValid() or
            any(type(face.Surface).__name__ != "Plane" for face in shape.Faces) or
            any(size <= tolerance for size in sizes) or
            abs(shape.Volume - math.prod(sizes)) > max(tolerance ** 3, shape.Volume * 1e-8)):
            return None
    thin_axes = [min(range(3), key=lambda axis: sizes[axis]) for sizes in dimensions]
    if thin_axes[0] != thin_axes[1]:
        return None
    thin = thin_axes[0]
    if any(sizes[thin] >= min(sizes[axis] for axis in range(3) if axis != thin) * 0.5
           for sizes in dimensions):
        return None
    if (abs(bounds[0][thin][0] - bounds[1][thin][0]) > tolerance or
        abs(bounds[0][thin][1] - bounds[1][thin][1]) > tolerance):
        return None
    end_axes = [axis for axis in range(3) if axis != thin and
                (abs(bounds[0][axis][1] - bounds[1][axis][0]) <= tolerance or
                 abs(bounds[1][axis][1] - bounds[0][axis][0]) <= tolerance)]
    if len(end_axes) != 1:
        return None
    end = end_axes[0]
    width = next(axis for axis in range(3) if axis not in (thin, end))
    shared_width = max(0.0, min(bounds[0][width][1], bounds[1][width][1]) -
                       max(bounds[0][width][0], bounds[1][width][0]))
    if shared_width <= tolerance:
        return None
    return {"subclass": "coplanar_orthogonal_plate_end_contact", "joint_kind": "butt",
            "status": "confirmed", "contact_area_mm2": shared_width * dimensions[0][thin],
            "contact_normal_axis": "XYZ"[end], "plate_thickness_axis": "XYZ"[thin],
            "opposed_normals": True, "rule_version": "customer.butt.orthogonal_plate.v1",
            "functional_role_status": "needs_review"}


# 先求精确最近距离；零距离再核验实体有效性及布尔交，区分正间隙、面/线/点接触和体积干涉。
# within_tolerance 只描述数值接近程度，微小正间隙不会因此升级为已相交。
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
                result["joint_classification"] = (orthogonal_plate_overlap(left, right, tolerance,
                                                                              minimum_lap_fraction) or
                                                  orthogonal_plate_butt(left, right, tolerance))
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
                result["joint_classification"] = (orthogonal_plate_overlap(left, right, tolerance,
                                                                              minimum_lap_fraction) or
                                                  orthogonal_plate_butt(left, right, tolerance))
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


# 一次加载限定实例集合，按包围盒距离筛选不同实例对；超过实体、面或候选对预算就明确失败。
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
            "source": "auxiliary_brep", "algorithm_version": "assembly.p6c.v3",
            "diagnostics": {"load_ms": round(context.load_ms, 3),
                            "compute_ms": round((time.perf_counter() - started) * 1000, 3),
                            "loaded_shapes": context.loaded_shapes, "pair_count": len(records)},
            "kernel": "OpenCascade", "kernel_version": str(getattr(Part, "OCC_VERSION", "unknown") or "unknown"),
            "freecad_version": ".".join(str(value) for value in FreeCAD.Version()[:3])}


# 读取隔离任务并写出状态/诊断；FreeCAD 版本和 OpenCascade 版本分别由 run 返回。
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
