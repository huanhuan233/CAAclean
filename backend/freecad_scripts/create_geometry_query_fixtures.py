"""Generate synthetic B-Rep acceptance shapes inside FreeCAD for integration tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD
import Part


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    output = Path(job["fixture_dir"])
    output.mkdir(parents=True, exist_ok=True)
    plate = Part.makeBox(20, 10, 4)
    hole = Part.makeCylinder(2, 4, FreeCAD.Vector(10, 5, 0))
    perforated = plate.cut(hole)
    hollow = Part.makeBox(20, 10, 10).cut(Part.makeBox(18, 8, 6, FreeCAD.Vector(1, 1, 2)))
    shapes = {
        "plate": plate,
        "plate_top": max(plate.Faces, key=lambda face: face.CenterOfMass.z),
        "plate_bottom": min(plate.Faces, key=lambda face: face.CenterOfMass.z),
        "perforated": perforated,
        "hollow": hollow,
        "hollow_top": max(hollow.Faces, key=lambda face: face.CenterOfMass.z),
        "point_a": Part.Vertex(FreeCAD.Vector(0, 0, 0)),
        "point_b": Part.Vertex(FreeCAD.Vector(3, 4, 0)),
        "point_outside": Part.Vertex(FreeCAD.Vector(30, 5, 4)),
        "finite_edge": Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1, 0, 0)),
        "edge_point": Part.Vertex(FreeCAD.Vector(3, 1, 0)),
        "edge_x": Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1, 0, 0)),
        "edge_y": Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 1, 0)),
    }
    for name, shape in shapes.items():
        shape.exportBrep(str(output / (name + ".brep")))
    Path(job["result_json_path"]).write_text(json.dumps({"status": "success", "names": list(shapes)}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
