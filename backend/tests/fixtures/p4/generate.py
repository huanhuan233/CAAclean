"""Independent P4 construction dimensions; run inside FreeCADCmd console."""

from pathlib import Path

import FreeCAD as App
import Part

target = Path(__file__).resolve().parent
v = App.Vector
block = Part.makeBox(80, 60, 30)


def save(name, shape):
    output = target / (name + ".stp")
    shape.exportStep(str(output))
    output.write_bytes(b"\n".join(line.rstrip() for line in output.read_bytes().splitlines()) + b"\n")


save("rect_boss", block.fuse(Part.makeBox(16, 12, 8, v(32, 24, 30))).removeSplitter())
save("rect_pocket", block.cut(Part.makeBox(16, 12, 8, v(32, 24, 22))).removeSplitter())
save("open_slot", block.cut(Part.makeBox(20, 12, 8, v(-1, 24, 22))).removeSplitter())
save("straight_rib", block.fuse(Part.makeBox(50, 3, 10, v(15, 28.5, 30))).removeSplitter())
save("thin_plate", Part.makeBox(60, 40, 3))
save("tee_flange", Part.makeBox(60, 3, 30).fuse(Part.makeBox(60, 12, 3, v(0, -4.5, 27))).removeSplitter())
pocket = block.cut(Part.makeBox(16, 12, 8, v(32, 24, 22))).removeSplitter()
bottom_edge = next(edge for edge in pocket.Edges if abs(edge.Length-16) < 1e-6
                   and abs(edge.CenterOfMass.y-24) < 1e-6 and abs(edge.CenterOfMass.z-22) < 1e-6)
save("pocket_bottom_fillet", pocket.makeFillet(2, [bottom_edge]))
save("boss_rib_distance", block.fuse(Part.makeCylinder(5, 8, v(15, 30, 30)))
     .fuse(Part.makeBox(30, 3, 10, v(40, 28.5, 30))).removeSplitter())
