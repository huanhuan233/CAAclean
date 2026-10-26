# 精确几何查询内核：在隔离的 FreeCAD 进程中读取后端已验证的 B-Rep 快照资产。
# 交互测量和批量识别共用求值逻辑；毫米容差与显示网格弦差分开处理。

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


# 将内核向量转为可写入 JSON 的三个浮点数，不做显示精度截断。
def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


# 将坐标序列转换为内核向量；面向用户的输入须先经过 finite_point 校验。
def vector(values):
    return FreeCAD.Vector(*[float(value) for value in values])


# 读取 B-Rep 并要求恰有一个指定类别的子形状；类别或数量不符按引用失效处理。
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


# 拒绝 null、布尔值、非三维坐标、NaN 和无穷，返回可安全求值的点向量。
def finite_point(values):
    if not isinstance(values, list) or len(values) != 3 or any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values
    ):
        raise ValueError("invalid_input: point must be finite XYZ")
    return vector(values)


# 读取当前有限几何的轴对齐包围盒，用于详情和计算范围估计。
def bbox(shape):
    b = shape.BoundBox
    return {"min": [b.XMin, b.YMin, b.ZMin], "max": [b.XMax, b.YMax, b.ZMax]}


# 精确点和显示命中种子必须二选一，并仅向当前有限边/面求最近点。
# 精确点使用计算容差，网格种子另有受限弦差余量；返回输入、实际投影点与残差，多个解明确拒绝。
def evaluated_point(shape, exact=None, seed=None, tolerance=0.0001, display_deflection=0.1):
    if (exact is None) == (seed is None):
        raise ValueError("invalid_input: one exact point or display seed required")
    supplied = finite_point(exact if exact is not None else seed)
    residual, pairs, _ = shape.distToShape(Part.Vertex(supplied))
    if not pairs:
        raise ValueError("unsupported: closest point unavailable")
    # Display tessellation has a separate, bounded residual allowance. Exact
    # user coordinates never inherit it; the actual projected point is reported.
    limit = tolerance if exact is not None else min(0.5, tolerance + 1.5 * display_deflection)
    if residual > limit:
        raise ValueError("invalid_input: point outside selected trimmed geometry")
    if len(pairs) != 1:
        raise ValueError("unsupported: multiple closest points on selected geometry")
    projected = pairs[0][0]
    return projected, {"input_kind": "exact_point" if exact is not None else "display_seed",
                       "input_point": xyz(supplied), "point": xyz(projected),
                       "residual_mm": float(residual), "acceptance_limit_mm": limit,
                       "display_deflection_mm": display_deflection if seed is not None else None,
                       "solution_count": len(pairs)}


# 复用统一点位核验后求有向面法向；零法向视为不支持，不返回虚构方向。
def face_normal(face, exact=None, seed=None, tolerance=0.0001, display_deflection=0.1):
    point, location = evaluated_point(face, exact, seed, tolerance, display_deflection)
    u, v = face.Surface.parameter(point)
    normal = face.normalAt(u, v)
    if normal.Length <= 1.0e-12:
        raise ValueError("unsupported: zero surface normal")
    normal.normalize()
    return normal, location


# 按顶点、边、面、实体读取各自的精确几何量；仅在提供求值位置时返回面局部法向。
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
        if params.get("point") is not None or params.get("seed_point") is not None:
            normal, location = face_normal(shape, params.get("point"), params.get("seed_point"),
                                           params.get("tolerance_mm", 0.0001),
                                           params.get("display_deflection_mm", 0.1))
            result["normal_at_point"] = xyz(normal)
            result["evaluation_location"] = location
    elif kind == "solid":
        result.update(volume_mm3=float(shape.Volume), surface_area_mm2=float(shape.Area),
                      face_count=len(shape.Faces), edge_count=len(shape.Edges))
    else:
        raise ValueError("unsupported: detail type")
    return {"status": "success", "values": result, "unit": "mm"}


# 返回内核最近点对和距离；within_tolerance 不代表相交，交互距离接口不执行布尔相交判定。
def distance(a, b, tolerance):
    value, point_pairs, _ = a.distToShape(b)
    if not point_pairs:
        return {"status": "empty", "values": None, "diagnostic": "no nearest points"}
    pairs = [{"a": xyz(left), "b": xyz(right)} for left, right in point_pairs[:16]]
    return {"status": "multiple" if len(point_pairs) > 1 else "success",
            "values": {"distance_mm": float(value), "nearest_points": pairs,
                       "within_tolerance": bool(value <= tolerance),
                       "intersection_status": "not_evaluated", "solution_count": len(point_pairs)},
            "unit": "mm"}


# 直线/平面可直接给方向，曲边/曲面必须有核验点；曲边还检查有限修剪参数区间。
def direction(shape, exact, seed, tolerance, display_deflection):
    kind = shape.ShapeType.lower()
    if kind == "edge":
        if type(shape.Curve).__name__ != "Line":
            if exact is None and seed is None:
                raise ValueError("invalid_input: curve tangent needs a point")
            point, evaluated = evaluated_point(shape, exact, seed, tolerance, display_deflection)
            param = shape.Curve.parameter(point)
            if param < shape.FirstParameter - 1e-9 or param > shape.LastParameter + 1e-9:
                raise ValueError("invalid_input: curve parameter outside trimmed edge")
            tangent = shape.tangentAt(param)
        else:
            if len(shape.Vertexes) < 2:
                raise ValueError("unsupported: edge has no endpoints")
            tangent = shape.Vertexes[-1].Point - shape.Vertexes[0].Point
            evaluated = None
        if tangent.Length <= 1.0e-12:
            raise ValueError("unsupported: zero tangent")
        tangent.normalize()
        return tangent, "line", evaluated
    if kind == "face":
        if exact is None and seed is None:
            if type(shape.Surface).__name__ != "Plane":
                raise ValueError("invalid_input: curved face needs a point")
            u0, u1, v0, v1 = shape.ParameterRange
            normal = shape.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            normal.normalize()
            return normal, "plane", None
        normal, evaluated = face_normal(shape, exact, seed, tolerance, display_deflection)
        return normal, "plane", evaluated
    raise ValueError("unsupported: angle object type")


# 基于两侧实际切向/法向计算无向角或向量夹角，保留求值位置及定义，不推断材料内外角。
def angle(a, b, params, tolerance):
    deflection = params.get("display_deflection_mm", 0.1)
    left, left_kind, left_location = direction(a, params.get("point_a"), params.get("seed_point_a"), tolerance, deflection)
    right, right_kind, right_location = direction(b, params.get("point_b"), params.get("seed_point_b"), tolerance, deflection)
    cosine = max(-1.0, min(1.0, left.dot(right)))
    # acos 的输入先夹紧，避免浮点点积略超 [-1, 1]；无向角忽略方向正负。
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
            "direction_a": xyz(left), "direction_b": xyz(right),
            "evaluation_a": left_location, "evaluation_b": right_location}, "unit": "deg"}


# 以给定原点和法向构造足够大的有限平面，与实体求交得到区域和截线。
# 相切单列 contact_only；显示点截断时标记 display_complete=false，不影响内核测量值。
def section(solid, params, tolerance):
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
        separation = solid.distToShape(plane)[0]
        return {"status": "contact_only" if separation <= tolerance else "empty",
                "values": {"regions": [], "curves": [], "net_area_mm2": 0.0}, "unit": "mm"}
    regions = [{"area_mm2": float(face.Area), "boundary_count": len(face.Wires),
                "perimeter_mm": float(sum(edge.Length for edge in face.Edges))} for face in common.Faces]
    curves = []
    for edge in common.Edges:
        sampled = edge.discretize(Deflection=0.1)
        curves.append({"length_mm": float(edge.Length),
                       "endpoints": [xyz(v.Point) for v in edge.Vertexes],
                       "display_points": [xyz(point) for point in sampled[:1000]],
                       "display_complete": len(sampled) <= 1000,
                       "display_sample_count": len(sampled)})
    return {"status": "success" if regions else "contact_only", "values": {
        "regions": regions, "net_area_mm2": sum(item["area_mm2"] for item in regions),
        "curves": curves, "region_count": len(regions), "display_deflection_mm": 0.1}, "unit": "mm"}


# 在核验点两侧探测材料方向，沿内法向求连续材料段；这里只证明单点局部法向厚度。
def local_thickness(face, solid, params, tolerance):
    if face.ShapeType != "Face" or solid.ShapeType != "Solid" or not solid.isClosed():
        raise ValueError("unsupported: thickness requires face and closed solid")
    normal, location = face_normal(face, params.get("point"), params.get("seed_point"), tolerance,
                                   params.get("display_deflection_mm", 0.1))
    point = vector(location["point"])
    epsilon = max(tolerance * 2.0, solid.BoundBox.DiagonalLength * 1.0e-7)
    inside_plus = solid.isInside(point + normal * epsilon, tolerance, False)
    inside_minus = solid.isInside(point - normal * epsilon, tolerance, False)
    if inside_plus == inside_minus:
        # 两侧都在材料内或都在外，无法唯一决定内法向；不能靠面朝向直接猜厚度方向。
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
            "material_intervals": [[0.0, thickness]], "sample_count": 1,
            "evaluation_location": location}, "unit": "mm"}


# 集中分派详情、距离、夹角、截面和局部厚度，共享任务给定的计算容差与显示弦差。
def execute_query(operation, shapes, params, tolerance, display_deflection=0.1):
    params = dict(params or {})
    params["tolerance_mm"] = tolerance
    params["display_deflection_mm"] = display_deflection
    if operation == "detail":
        result = detail(shapes[0], params)
    elif operation == "distance":
        result = distance(shapes[0], shapes[1], tolerance)
    elif operation == "angle":
        result = angle(shapes[0], shapes[1], params, tolerance)
    elif operation == "section":
        result = section(shapes[0], params, tolerance)
    elif operation == "local_thickness":
        result = local_thickness(shapes[0], shapes[1], params, tolerance)
    else:
        raise ValueError("unsupported: operation")
    return result


# 单任务几何上下文：按资产路径及类别缓存内核形状，统计加载次数、耗时和查询次数。
class GeometryKernelContext:
    """One isolated task loads each B-Rep once and reuses exact kernel operations."""

    # 限制资产数量及文件总大小，同一资产/类别只读取一次；缓存随本次子进程任务结束释放。
    def __init__(self, paths, kinds, tolerance, display_deflection=0.1):
        if len(paths) != len(kinds) or len(paths) > 256:
            raise ValueError("invalid_input: geometry asset count exceeds task limit")
        if sum(Path(path).stat().st_size for path in set(paths)) > 512 * 1024 * 1024:
            raise ValueError("invalid_input: geometry task exceeds 512 MiB asset limit")
        self.tolerance = tolerance
        self.display_deflection = display_deflection
        self.shapes = []
        loaded = {}
        # 这是当前任务内的缓存，不是跨请求常驻 FreeCAD 服务。
        started = time.perf_counter()
        for path, kind in zip(paths, kinds):
            key = (path, kind)
            if key not in loaded:
                loaded[key] = shape_at(path, kind)
            self.shapes.append(loaded[key])
        self.loaded_shapes = len(loaded)
        self.load_ms = (time.perf_counter() - started) * 1000.0
        self.query_count = 0

    # 校验批量查询的资产下标后调用同一计算入口，不为每张面另启进程。
    def query(self, operation, indices, params):
        if not isinstance(indices, list) or not indices or len(indices) > 2 or any(
            not isinstance(index, int) or index < 0 or index >= len(self.shapes) for index in indices
        ):
            raise ValueError("invalid_input: invalid batch asset indices")
        self.query_count += 1
        return execute_query(operation, [self.shapes[index] for index in indices], params,
                             self.tolerance, self.display_deflection)


# 创建一次上下文，执行单项或最多 500 条批量查询；批量中的可解释错误按项返回。
def run(job):
    tolerance = float(job.get("tolerance_mm", 0.01))
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("invalid_input: positive finite tolerance required")
    deflection = float(job.get("display_deflection_mm", 0.1))
    if not math.isfinite(deflection) or deflection <= 0 or deflection > 1:
        raise ValueError("invalid_input: display deflection out of range")
    context = GeometryKernelContext(job["asset_paths"], job["asset_kinds"], tolerance, deflection)
    started = time.perf_counter()
    if job["operation"] == "batch":
        queries = job.get("queries")
        if not isinstance(queries, list) or len(queries) > 500:
            raise ValueError("invalid_input: batch query limit is 500")
        results = []
        for query in queries:
            try:
                results.append(context.query(query["operation"], query["asset_indices"], query.get("parameters")))
            except (ValueError, KeyError, IndexError) as exc:
                code, _, message = str(exc).partition(":")
                results.append({"status": code if code in {"invalid_input", "unsupported"} else "failed",
                                "values": None, "diagnostic": message.strip() or str(exc)})
        result = {"status": "success", "results": results}
    else:
        result = context.query(job["operation"], list(range(len(context.shapes))), job.get("parameters"))
    result["diagnostics"] = {"load_ms": round(context.load_ms, 3),
                             "query_ms": round((time.perf_counter() - started) * 1000.0, 3),
                             "loaded_shapes": context.loaded_shapes, "query_count": context.query_count,
                             "cache_hit": context.loaded_shapes < len(context.shapes)}
    result["kernel"] = "OpenCascade"
    result["kernel_version"] = str(getattr(Part, "OCC_VERSION", "unknown") or "unknown")
    result["freecad_version"] = ".".join(str(value) for value in FreeCAD.Version()[:3])
    return result


# 处理任务文件协议，捕获业务与内核异常并输出明确状态，避免失败被包装成正常空结果。
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
