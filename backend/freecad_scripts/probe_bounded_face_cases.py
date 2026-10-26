# 裁剪面点位回归探针：构造带孔板、偏心孔、凹多边形和完整圆盘。
# 用于验证孔内点、边界点与实际材料面内部点不会被混淆，不注入业务列表。

"""Independent exact-face cases for trimmed point classification tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD
import Part

from bounded_face_evidence import trimmed_face_point_status


# 按预设构造坐标选取反例点，调用裁剪面判定并将逐案例证据写回测试结果。
def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    v = FreeCAD.Vector
    ring = Part.makeBox(20, 20, 2).cut(Part.makeCylinder(3, 2, v(10, 10, 0)))
    ring_top = max((face for face in ring.Faces if type(face.Surface).__name__ == "Plane"),
                   key=lambda face: face.CenterOfMass.z)
    offset = Part.makeBox(20, 20, 2).cut(Part.makeCylinder(2, 2, v(5, 10, 0)))
    offset_top = max((face for face in offset.Faces if type(face.Surface).__name__ == "Plane"),
                     key=lambda face: face.CenterOfMass.z)
    polygon = Part.makePolygon([v(*point) for point in
                                [(0, 0, 0), (10, 0, 0), (10, 10, 0),
                                 (5, 10, 0), (5, 5, 0), (0, 5, 0), (0, 0, 0)]])
    concave = Part.Face(polygon)
    disc = max((face for face in Part.makeCylinder(5, 2).Faces
                if type(face.Surface).__name__ == "Plane"), key=lambda face: face.CenterOfMass.z)
    cases = {
        "annular_hole": (ring_top, v(10, 10, 2)),
        "annular_boundary": (ring_top, v(13, 10, 2)),
        "annular_material": (ring_top, v(15, 10, 2)),
        "offset_hole": (offset_top, v(5, 10, 2)),
        "concave_outside": (concave, v(3, 7, 0)),
        "concave_inside": (concave, v(7, 7, 0)),
        "complete_disc": (disc, v(0, 0, 2)),
    }
    output = {name: trimmed_face_point_status(face, point, 1e-6)
              for name, (face, point) in cases.items()}
    Path(job["result_json_path"]).write_text(json.dumps(output), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
