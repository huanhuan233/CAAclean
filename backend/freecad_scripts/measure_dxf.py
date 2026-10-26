# DXF 几何辅助核验：接收宿主解析器输出的中性文档，对折线构造真实内核边和面。
# 对象坐标系 OCS 的弓高点转换到世界坐标 WCS 后再构造圆弧，保持挤出方向与标高。

"""FreeCAD background validation of neutral DXF wires and planar faces."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import FreeCAD as App
import Part


# 把已解析的三维坐标转换为 FreeCAD 向量，保持输入文档使用的坐标单位。
def vector(values):
    return App.Vector(float(values[0]), float(values[1]), float(values[2]))


# 按折线的闭合标志连接顶点；bulge 为零构造直线，否则利用弓高构造有限圆弧。
# 零长度段直接失败，避免生成无效 Wire；圆弧中点使用与宿主解析器一致的 OCS 基底。
def edges_for(record):
    vertices = record["world_vertices"]
    source = record["vertices"]
    count = len(vertices) if record["closed"] else len(vertices) - 1
    edges = []
    for index in range(count):
        end_index = (index + 1) % len(vertices)
        start, end = vector(vertices[index]), vector(vertices[end_index])
        if (end - start).Length < 1e-12:
            raise ValueError("zero_length_segment")
        bulge = float(source[index][4])
        if abs(bulge) < 1e-12:
            edges.append(Part.makeLine(start, end))
            continue
        x1, y1 = source[index][:2]
        x2, y2 = source[end_index][:2]
        mid_x = (x1 + x2) / 2 - (y2 - y1) * bulge / 2
        mid_y = (y1 + y2) / 2 + (x2 - x1) * bulge / 2
        extrusion = record["extrusion"]
        ocs = App.Vector(*extrusion)
        # The host parser supplies WCS vertices; derive the OCS middle point using
        # the same arbitrary-axis convention as ezdxf before constructing Part.Arc.
        if abs(ocs.x) < 1 / 64 and abs(ocs.y) < 1 / 64:
            x_axis = App.Vector(0, 1, 0).cross(ocs)
        else:
            x_axis = App.Vector(0, 0, 1).cross(ocs)
        x_axis.normalize()
        y_axis = ocs.cross(x_axis)
        middle = x_axis * mid_x + y_axis * mid_y + ocs * float(record["elevation"])
        edges.append(Part.Arc(start, middle, end).toShape())
    return edges


# 逐对象核验折线长度，闭合且有效时才计算平面面积；单个对象失败保留其错误而不阻断其余对象。
def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    document = json.loads(Path(job["document_path"]).read_text(encoding="utf-8"))
    measurements = {}
    for record in [*document["entities"], *document.get("occurrences", [])]:
        if record.get("status") or record["type"] not in {"LWPOLYLINE", "POLYLINE"}:
            continue
        try:
            edges = edges_for(record)
            wire = Part.Wire(edges)
            if not wire.isValid():
                raise ValueError("invalid_wire")
            item = {"status": "validated", "wire_length": float(wire.Length), "face_area": None}
            if record["closed"]:
                if not wire.isClosed():
                    raise ValueError("open_wire")
                face = Part.Face(wire)
                if not face.isValid():
                    raise ValueError("invalid_face")
                item["face_area"] = float(face.Area)
            measurements[record["object_id"]] = item
        except Exception as exc:
            measurements[record["object_id"]] = {"status": "invalid", "reason": str(exc)}
    Path(job["result_json_path"]).write_text(json.dumps({"measurements": measurements}), encoding="utf-8")


if __name__ == "__main__":
    main()
