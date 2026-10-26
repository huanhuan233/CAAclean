# 复材平面覆盖计算：对已验证共面的铺层采样轮廓进行分区，保留每个物理单层 ID。
# 轮廓是带采样误差的输入，输出面积不是任意弯曲铺层的真实曲面面积，也不推断参考面。

"""Partition already validated, coplanar native ply contours in one FreeCAD task.

Input polygons are display samples with an explicit sampling error. This job
does not infer a reference surface or merge distinct physical ply identities.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import FreeCAD
import Part


MAX_PLIES = 64
MAX_CELLS = 512
MAX_VERTICES = 4096
AREA_TOLERANCE = 1e-6


# 验证三维有限坐标及点数预算，闭合采样多边形以构造平面边界。
def _wire(points):
    if not isinstance(points, list) or not 3 <= len(points) <= MAX_VERTICES:
        raise ValueError("invalid_input: invalid contour point count")
    vectors = []
    for point in points:
        if not isinstance(point, list) or len(point) != 3 or not all(
            isinstance(value, (int, float)) and math.isfinite(value) for value in point
        ):
            raise ValueError("invalid_input: nonfinite contour point")
        vectors.append(FreeCAD.Vector(*point))
    vectors.append(vectors[0])
    return Part.makePolygon(vectors)


# 将外轮廓组成区域并扣除内孔；检查区域有效性，禁止把损坏轮廓当成零面积铺层。
def _ply_shape(ply):
    loops = ply.get("loops")
    if not isinstance(loops, list) or not loops or len(loops) > 128:
        raise ValueError("invalid_input: invalid ply loops")
    outer = []
    holes = []
    for loop in loops:
        face = Part.Face(_wire(loop["sampled_points_mm"]))
        if not face.isValid() or face.Area <= AREA_TOLERANCE:
            raise ValueError("geometry_unavailable: invalid planar ply region")
        (outer if loop.get("role") == "outer" else holes).append(face)
    if not outer:
        raise ValueError("invalid_input: no outer loop")
    shape = Part.makeCompound(outer)
    for hole in holes:
        shape = shape.cut(hole)
    if not shape.isValid():
        raise ValueError("geometry_unavailable: invalid ply with holes")
    return shape


# 仅保留大于面积容差的面，用于去除布尔分割产生的微小区域。
def _faces(shape):
    return [face for face in shape.Faces if face.Area > AREA_TOLERANCE]


# 将一个覆盖分区写成面积、所属单层 ID 和受限显示网格；网格只负责展示。
def _cell(face, ids):
    vertices, triangles = face.tessellate(0.05)
    if len(triangles) > 10000:
        raise ValueError("unsupported: region display triangle budget exceeded")
    return {
        "ply_object_ids": ids,
        "area_mm2": face.Area,
        "display_vertices_mm": [[point.x, point.y, point.z] for point in vertices],
        "display_triangles": [list(triangle) for triangle in triangles],
    }


# 在端点共线的边界中求有限重叠区间，用于标记覆盖分区间的直线过渡边。
def _shared_straight_segments(face_a, face_b):
    for edge_a in face_a.Edges:
        va = edge_a.Vertexes
        if len(va) != 2 or edge_a.Length <= 1e-5:
            continue
        a, b = va[0].Point, va[1].Point
        direction = b.sub(a)
        length = direction.Length
        direction.normalize()
        for edge_b in face_b.Edges:
            vb = edge_b.Vertexes
            if len(vb) != 2 or edge_b.Length <= 1e-5:
                continue
            c, d = vb[0].Point, vb[1].Point
            if (c.sub(a).cross(direction).Length > 1e-4 or
                    d.sub(a).cross(direction).Length > 1e-4):
                continue
            lo = max(0.0, min(c.sub(a).dot(direction), d.sub(a).dot(direction)))
            hi = min(length, max(c.sub(a).dot(direction), d.sub(a).dot(direction)))
            if hi - lo > 1e-5:
                yield (FreeCAD.Vector(a.x + direction.x*lo, a.y + direction.y*lo, a.z + direction.z*lo),
                       FreeCAD.Vector(a.x + direction.x*hi, a.y + direction.y*hi, a.z + direction.z*hi),
                       hi - lo)


# 逐层用交集和差集细分覆盖区域，同时累积该区域的单层身份；控制单层数和分区数预算。
def run(job):
    plies = job.get("plies")
    if not isinstance(plies, list) or not 1 <= len(plies) <= MAX_PLIES:
        raise ValueError("invalid_input: ply count out of range")
    cells = []
    for ply in plies:
        ply_id = ply.get("object_id")
        if not isinstance(ply_id, str) or not ply_id:
            raise ValueError("invalid_input: missing ply id")
        shape = _ply_shape(ply)
        previous = cells
        next_cells = []
        for face, ids in previous:
            next_cells.extend((piece, ids) for piece in _faces(face.cut(shape)))
            next_cells.extend((piece, ids + [ply_id]) for piece in _faces(face.common(shape)))
        previous_union = Part.makeCompound([face for face, _ in previous]) if previous else None
        uncovered = shape.cut(previous_union) if previous_union else shape
        next_cells.extend((piece, [ply_id]) for piece in _faces(uncovered))
        if len(next_cells) > MAX_CELLS:
            raise ValueError("unsupported: coverage cell budget exceeded")
        cells = next_cells
    transitions = []
    if len(cells) <= 128:
        for left, (face_a, ids_a) in enumerate(cells):
            for right in range(left + 1, len(cells)):
                face_b, ids_b = cells[right]
                if set(ids_a) == set(ids_b):
                    continue
                for start, end, length in _shared_straight_segments(face_a, face_b):
                    transitions.append({
                        "cell_a": left, "cell_b": right,
                        "start_mm": [start.x, start.y, start.z],
                        "end_mm": [end.x, end.y, end.z],
                        "length_mm": length,
                        "kind": "internal_ply_termination" if set(ids_a) & set(ids_b) else "adjacent_distinct_coverage",
                        "ending_ply_object_ids": sorted(set(ids_a) - set(ids_b)),
                        "starting_ply_object_ids": sorted(set(ids_b) - set(ids_a)),
                    })
    return {
        "status": "computed", "method": "FreeCAD_Part_coplanar_face_boolean_v1",
        "cells": [_cell(face, ids) for face, ids in cells],
        "transitions": transitions,
        "transition_status": "computed" if len(cells) <= 128 else "unsupported_cell_budget",
        "freecad_version": ".".join(str(v) for v in FreeCAD.Version()[:3]),
        "kernel_version": str(getattr(Part, "OCC_VERSION", "unknown") or "unknown"),
    }


# 读取复材作业并输出分区或明确失败状态；失败时的空 cells 不代表成功计算出零覆盖。
def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(job)
    except ValueError as exc:
        code, _, message = str(exc).partition(":")
        result = {"status": code if code in {"invalid_input", "unsupported", "geometry_unavailable"} else "failed",
                  "diagnostic": message.strip() or str(exc), "cells": []}
    except Exception as exc:
        result = {"status": "failed", "diagnostic": type(exc).__name__ + ": " + str(exc), "cells": []}
    Path(job["result_json_path"]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
