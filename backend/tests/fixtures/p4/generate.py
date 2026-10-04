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
