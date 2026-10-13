"""Independent OCC fixture construction; radii 4/3, bend center radius 30 mm."""
import json
import math
import sys
from pathlib import Path

import FreeCAD as App
import Part

job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
root = Path(job['directory'])
root.mkdir(parents=True, exist_ok=True)

def elbow(radius, angle=90):
    return Part.makeTorus(30, radius, App.Vector(), App.Vector(0, 0, 1), -180, 180, angle)

def pipe(radius):
    return elbow(radius).fuse(Part.makeCylinder(radius, 20, App.Vector(30, -20, 0), App.Vector(0, 1, 0))).fuse(
        Part.makeCylinder(radius, 40, App.Vector(0, 30, 0), App.Vector(-1, 0, 0))).removeSplitter()

pure = elbow(4).cut(elbow(3)).removeSplitter()
combo = pipe(4).cut(pipe(3)).removeSplitter()
# Fuse two halves without removeSplitter, preserving split wall faces.
halves = combo.cut(Part.makeBox(150, 150, 30, App.Vector(-60, -60, 0))).fuse(
    combo.common(Part.makeBox(150, 150, 30, App.Vector(-60, -60, 0))))
transformed = halves.copy()
transformed.Placement = App.Placement(App.Vector(101, -83, 71), App.Rotation(App.Vector(1, 2, 3), 67))
shapes = dict(elbow=pure, combo=combo, split=halves, transformed=transformed,
              rod=pipe(4), closed=Part.makeTorus(30, 4).cut(Part.makeTorus(30, 3)),
              damaged=combo.cut(Part.makeBox(6, 10, 10, App.Vector(31, -15, -5))),
              eccentric=pipe(4).cut(pipe(3).translated(App.Vector(0, 0, 0.4))),
              neighbor=Part.makeSphere(1, App.Vector(37 / math.sqrt(2), 37 / math.sqrt(2), 0)))
for name, shape in shapes.items():
    shape.exportBrep(str(root / (name + '.brep')))
Path(job['result_json_path']).write_text(json.dumps({'status': 'success',
    'fixtures': {name: {'valid': shape.isValid(), 'solids': len(shape.Solids), 'faces': len(shape.Faces)}
                 for name, shape in shapes.items()},
    'expected': {'outer_diameter_mm': 8, 'inner_diameter_mm': 6, 'wall_thickness_mm': 1,
                 'elbow_length_mm': 15 * math.pi, 'combo_length_mm': 60 + 15 * math.pi}}), encoding='utf-8')
