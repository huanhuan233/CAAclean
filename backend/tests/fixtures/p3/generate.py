"""Recreate P3 STEP references with FreeCAD/OCCT; run inside FreeCADCmd."""

import FreeCAD as App
import Part
from pathlib import Path

target = Path(__file__).resolve().parent
target.mkdir(exist_ok=True)
v = App.Vector

def save(name, shape):
    output = target / (name + '.stp')
    shape.exportStep(str(output))
    normalize_step(output)

def normalize_step(path):
    path.write_bytes(b'\n'.join(line.rstrip() for line in path.read_bytes().splitlines()) + b'\n')

block = Part.makeBox(80, 60, 30)
save('block', block)
save('through', block.cut(Part.makeCylinder(5, 30, v(40,30,0))))
meter_file = target / 'through_m.stp'
Part.makeBox(.08, .06, .03).cut(Part.makeCylinder(.005, .03, v(.04,.03,0))).exportStep(str(meter_file))
meter_file.write_text(meter_file.read_text(encoding='latin-1').replace('SI_UNIT(.MILLI.,.METRE.)', 'SI_UNIT($,.METRE.)'), encoding='latin-1')
normalize_step(meter_file)
save('blind', block.cut(Part.makeCylinder(5, 15, v(40,30,15))))
save('conical_blind', block.cut(Part.makeCylinder(5, 15, v(40,30,15)).fuse(Part.makeCone(0, 5, 3, v(40,30,12)))))
save('shallow_large', block.cut(Part.makeCylinder(20, 2, v(40,30,28))))
save('boss', block.fuse(Part.makeCylinder(8, 15, v(40,30,30))))
save('half_slot', block.cut(Part.makeCylinder(5, 30, v(0,30,0))))
save('step', block.cut(Part.makeCylinder(5, 30, v(40,30,0))).cut(Part.makeCylinder(9, 5, v(40,30,25))))
save('mouth_chamfer', block.cut(Part.makeCylinder(5, 30, v(40,30,0)).fuse(Part.makeCone(5, 7, 2, v(40,30,28)))))
save('divider', block.cut(Part.makeCylinder(5, 8, v(40,30,0))).cut(Part.makeCylinder(5, 8, v(40,30,22))))
save('closed_cavity', block.cut(Part.makeCylinder(5, 14, v(40,30,8))))
edge = next(e for e in block.Edges if abs(e.Length-80) < 1e-6 and abs(e.CenterOfMass.y) < 1e-6 and abs(e.CenterOfMass.z) < 1e-6)
save('fillet', block.makeFillet(3, [edge]))
save('chamfer', block.makeChamfer(4, [edge]))
save('chamfer_unequal', block.makeChamfer(3, 6, [edge]))
save('through_transformed', block.cut(Part.makeCylinder(5, 30, v(40,30,0))).copy().transformShape(
    App.Matrix(0, -1, 0, 120, 1, 0, 0, -20, 0, 0, 1, 7, 0, 0, 0, 1), True))
second = block.cut(Part.makeCylinder(5, 30, v(40,30,0))).copy()
second.translate(v(120,0,0))
save('two_solids', Part.makeCompound([block.cut(Part.makeCylinder(5, 30, v(40,30,0))), second]))
# One connected U-shaped Solid. The first wall has a through hole, while a
# remote bridge-supported slab intersects the same infinite centerline later.
near_wall = block.cut(Part.makeCylinder(5, 30, v(40,30,0)))
bridge = Part.makeBox(10, 60, 20, v(0,0,30))
far_wall = Part.makeBox(80, 60, 10, v(0,0,50))
save('remote_material_after_through', near_wall.fuse(bridge).fuse(far_wall).removeSplitter())
