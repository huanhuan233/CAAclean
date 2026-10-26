# 由原生有序边采样构造平面轮廓；面积属于轮廓平面，不能当作曲面铺层面积。
"""Conservative planar contour derivation from ordered native edge uses.

The area belongs to the contour plane. It is not a curved ply surface area.
"""

from __future__ import annotations

import math
from typing import Any


Point = tuple[float, float, float]


# 将三元坐标转为有限浮点向量，不完整或非有限坐标返回空值。
def _point(value: Any) -> Point | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        result = tuple(float(number) for number in value)
    except (TypeError, ValueError):
        return None
    return result if all(math.isfinite(number) for number in result) else None  # type: ignore[return-value]


# 计算两点位移，用于建立局部平面基和检验共面性。
def _sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


# 计算三维点积，用于平面投影及向量长度。
def _dot(a: Point, b: Point) -> float:
    return sum(x * y for x, y in zip(a, b))


# 计算三维叉积，用于确定轮廓法向和第二平面轴。
def _cross(a: Point, b: Point) -> Point:
    return a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]


# 归一化向量，退化向量返回空值以阻止虚构平面方向。
def _unit(a: Point) -> Point | None:
    length = math.sqrt(_dot(a, a))
    return tuple(x/length for x in a) if length > 1e-12 else None  # type: ignore[return-value]


# 计算三维欧氏距离，作为边连接与端点一致性判断依据。
def _distance(a: Point, b: Point) -> float:
    return math.dist(a, b)


# 仅采样直线和可验证圆弧；圆弧按弦高限制分段并核对原生端点。
def _edge_points(edge: dict[str, Any], sagitta_mm: float) -> tuple[list[Point], float] | None:
    kind = edge.get("curve_type")
    if kind == "line":
        start, end = _point(edge.get("start_mm")), _point(edge.get("end_mm"))
        return ([start, end], 0.0) if start and end and start != end else None
    if kind != "circle":
        return None
    center = _point(edge.get("center_mm"))
    u = _unit(_point(edge.get("axis_u")) or (0, 0, 0))
    v = _unit(_point(edge.get("axis_v")) or (0, 0, 0))
    try:
        radius = float(edge["radius_mm"])
        start_angle = float(edge["curve_start_param"])
        end_angle = float(edge["curve_end_param"])
    except (ValueError, TypeError, KeyError):
        return None
    sweep = end_angle - start_angle
    if (not center or not u or not v or not all(math.isfinite(x) for x in (radius, sweep))
            or radius <= 0 or abs(sweep) < 1e-9 or abs(sweep) > 2*math.pi + 1e-6
            or abs(_dot(u, v)) > 1e-5):
        return None
    max_angle = 2 * math.acos(max(-1.0, min(1.0, 1 - sagitta_mm / radius)))
    segments = max(16, math.ceil(abs(sweep) / max_angle))
    if segments > 2048:
        return None
    points: list[Point] = []
    for index in range(segments + 1):
        angle = start_angle + sweep * index / segments
        points.append(tuple(center[axis] + radius * (u[axis]*math.cos(angle) + v[axis]*math.sin(angle))
                            for axis in range(3)))  # type: ignore[arg-type]
    start_vertex, end_vertex = _point(edge.get("start_mm")), _point(edge.get("end_mm"))
    if start_vertex and _distance(start_vertex, points[0]) > max(0.01, sagitta_mm):
        return None
    if end_vertex and _distance(end_vertex, points[-1]) > max(0.01, sagitta_mm):
        return None
    return points, sagitta_mm


# 保持采集边顺序，仅尝试反转边方向，要求所有连接及首尾闭合满足容差。
def _assemble_loop(edges: list[dict[str, Any]], tolerance_mm: float, sagitta_mm: float) -> tuple[list[Point], float] | None:
    sampled = [_edge_points(edge, sagitta_mm) for edge in edges]
    if any(item is None for item in sampled):
        return None
    parts = [item[0] for item in sampled if item]
    error = max((item[1] for item in sampled if item), default=0.0)
    for first in (parts[0], list(reversed(parts[0]))):
        chain = list(first)
        valid = True
        for part in parts[1:]:
            if _distance(chain[-1], part[0]) <= tolerance_mm:
                chain.extend(part[1:])
            elif _distance(chain[-1], part[-1]) <= tolerance_mm:
                chain.extend(list(reversed(part))[1:])
            else:
                valid = False
                break
        if valid and len(chain) >= 4 and _distance(chain[-1], chain[0]) <= tolerance_mm:
            return chain[:-1], error
    return None


# 按鞋带公式计算二维环有向面积，供内外环面积累计。
def _signed_area(points: list[tuple[float, float]]) -> float:
    return sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(points, points[1:]+points[:1])) / 2


# 用四个方向叉积检测严格交叉，容差用于排除数值噪声。
def _segment_intersects(a, b, c, d, tolerance: float) -> bool:
    # 计算二维转向量，判断第三点位于有向线段的哪一侧。
    def orient(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    o1, o2, o3, o4 = orient(a,b,c), orient(a,b,d), orient(c,d,a), orient(c,d,b)
    return (o1*o2 < -tolerance*tolerance and o3*o4 < -tolerance*tolerance)


# 检查环中非相邻线段的严格相交，跳过首尾相邻边。
def _self_intersects(points: list[tuple[float, float]], tolerance: float) -> bool:
    size = len(points)
    for i in range(size):
        for j in range(i+2, size):
            if i == 0 and j == size-1:
                continue
            if _segment_intersects(points[i], points[(i+1)%size], points[j], points[(j+1)%size], tolerance):
                return True
    return False


# 射线法判断点在环内外；落在容差边界上返回空值，交给上层拒绝歧义。
def _inside(point: tuple[float, float], polygon: list[tuple[float, float]], tolerance: float) -> bool | None:
    x, y = point
    inside = False
    for (x1,y1),(x2,y2) in zip(polygon, polygon[1:]+polygon[:1]):
        dx, dy = x2-x1, y2-y1
        cross = (x-x1)*dy - (y-y1)*dx
        if abs(cross) <= tolerance * max(1, math.hypot(dx,dy)) and (
            min(x1,x2)-tolerance <= x <= max(x1,x2)+tolerance and
            min(y1,y2)-tolerance <= y <= max(y1,y2)+tolerance):
            return None
        if (y1 > y) != (y2 > y) and x < x1 + dx * (y-y1) / dy:
            inside = not inside
    return inside


# 验证无重复边、闭合、共面及无交叉，再按嵌套奇偶确定孔洞并估计采样面积误差。
def derive_planar_regions(payload: Any, *, tolerance_mm: float = 1e-4,
                          sagitta_mm: float = 0.05) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "unsupported", "source": "derived_from_native_ordered_contour",
                              "area_mm2": None, "area_error_bound_mm2": None,
                              "outer_boundary_length_mm": None, "inner_boundary_length_mm": None,
                              "region_count": 0, "hole_count": 0, "loops": [],
                              "display_sampling_error_mm": sagitta_mm, "diagnostics": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("faces"), list):
        result["diagnostics"].append("native_boundary_missing")
        return result
    native_loops = [loop for face in payload["faces"] if isinstance(face, dict)
                    for loop in face.get("loops", []) if isinstance(loop, dict)]
    if not native_loops or len(native_loops) > 128:
        result["diagnostics"].append("loop_count_out_of_range")
        return result
    # 接缝或共享边会重复出现；此算法要求每条边恰好出现一次，拒绝自行修补拓扑。
    indices = [edge.get("edge_index") for loop in native_loops for edge in loop.get("edges", [])
               if isinstance(edge, dict)]
    if (not all(isinstance(index, int) and index > 0 for index in indices) or
        len(indices) != payload.get("visited_edge_occurrences") or
        len(set(indices)) != payload.get("expected_unique_edges") or
        len(set(indices)) != payload.get("visited_unique_edges") or
        len(indices) != len(set(indices))):
        result["diagnostics"].append("edge_coverage_or_seam_unverified")
        return result
    assembled = []
    for loop in native_loops:
        edges = loop.get("edges")
        if not isinstance(edges, list) or not edges:
            result["diagnostics"].append("empty_loop")
            return result
        item = _assemble_loop(edges, tolerance_mm, sagitta_mm)
        if item is None:
            result["diagnostics"].append("gap_or_unsupported_curve")
            return result
        length = sum(float(edge["length_mm"]) for edge in edges)
        if not math.isfinite(length) or length <= 0:
            result["diagnostics"].append("invalid_native_length")
            return result
        assembled.append((loop, item[0], item[1], length))
    all_points = [point for _, points, _, _ in assembled for point in points]
    origin = all_points[0]
    axis_u = next((_unit(_sub(point, origin)) for point in all_points
                   if _distance(point, origin) > tolerance_mm), None)
    if axis_u is None:
        result["diagnostics"].append("plane_undetermined")
        return result
    normal = next((_unit(_cross(axis_u, _sub(point, origin))) for point in all_points
                   if _unit(_cross(axis_u, _sub(point, origin))) is not None), None)
    if normal is None or any(abs(_dot(_sub(point, origin), normal)) > tolerance_mm for point in all_points):
        result["diagnostics"].append("nonplanar_or_degenerate")
        return result
    axis_v = _cross(normal, axis_u)
    planar = [[(_dot(_sub(point, origin), axis_u), _dot(_sub(point, origin), axis_v))
               for point in points] for _, points, _, _ in assembled]
    if any(_self_intersects(points, tolerance_mm) for points in planar):
        result["diagnostics"].append("self_intersection")
        return result
    for i, points in enumerate(planar):
        for j in range(i+1, len(planar)):
            if any(_segment_intersects(a,b,c,d,tolerance_mm)
                   for a,b in zip(points, points[1:]+points[:1])
                   for c,d in zip(planar[j], planar[j][1:]+planar[j][:1])):
                result["diagnostics"].append("intersecting_loops")
                return result
    areas = [abs(_signed_area(points)) for points in planar]
    if any(area <= tolerance_mm*tolerance_mm for area in areas):
        result["diagnostics"].append("zero_area_loop")
        return result
    area_total = 0.0
    area_error = 0.0
    outer_length = inner_length = 0.0
    for index, (source_loop, points_3d, error, length) in enumerate(assembled):
        containers = []
        for other, polygon in enumerate(planar):
            if other == index:
                continue
            relation = _inside(planar[index][0], polygon, tolerance_mm)
            if relation is None:
                result["diagnostics"].append("touching_loop_boundary")
                return result
            if relation:
                containers.append(other)
        role = "inner" if len(containers) % 2 else "outer"
        native_role = source_loop.get("location")
        if native_role in {"inner", "outer"} and native_role != role:
            result["diagnostics"].append("native_role_conflict")
            return result
        area_total += -areas[index] if role == "inner" else areas[index]
        # 用边长与最大弦高给出面积误差界，避免把采样多边形面积当成精确曲线积分。
        area_error += length * error + math.pi * error * error
        if role == "inner":
            result["hole_count"] += 1
            inner_length += length
        else:
            result["region_count"] += 1
            outer_length += length
        result["loops"].append({"role": role, "role_source": "native_domain" if native_role == role else "planar_containment",
                                "edge_indices": [edge["edge_index"] for edge in source_loop["edges"]],
                                "sampled_points_mm": [list(point) for point in points_3d],
                                "native_length_mm": length})
    result.update({"status": "derived_planar", "area_mm2": area_total,
                   "area_error_bound_mm2": area_error,
                   "outer_boundary_length_mm": outer_length,
                   "inner_boundary_length_mm": inner_length,
                   "plane": {"origin_mm": list(origin), "axis_u": list(axis_u),
                             "axis_v": list(axis_v), "normal": list(normal)}})
    return result
