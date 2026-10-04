"""B-Rep cases with partial overlap and centroids outside trimmed faces."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD
import Part

from parse_step import thin_wall_pair_evidence


def horizontal_face(shape, z, direction):
    for face in shape.Faces:
        if type(face.Surface).__name__ != "Plane" or abs(face.CenterOfMass.z-z) > 1e-6:
            continue
        u0, u1, v0, v1 = face.ParameterRange
        normal = face.normalAt((u0+u1)/2, (v0+v1)/2)
        if normal.z*direction > 0.9:
            return face
    raise ValueError("horizontal face unavailable")


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    v = FreeCAD.Vector
    stepped = Part.makeBox(60, 40, 3).fuse(Part.makeBox(20, 40, 3, v(40, 0, 3))).removeSplitter()
    large = horizontal_face(stepped, 0, -1)
    small = horizontal_face(stepped, 6, 1)
    base_top = horizontal_face(stepped, 3, 1)
    ring = Part.makeBox(30, 30, 3).cut(Part.makeCylinder(3, 3, v(15, 15, 0)))
    ring_top = horizontal_face(ring, 3, 1)
    ring_bottom = horizontal_face(ring, 0, -1)
    open_gap = (Part.makeBox(60, 20, 2)
                .fuse(Part.makeBox(60, 20, 2, v(0, 0, 8)))
                .fuse(Part.makeBox(5, 20, 6, v(0, 0, 2))).removeSplitter())
    gap_lower = horizontal_face(open_gap, 2, 1)
    gap_upper = horizontal_face(open_gap, 8, -1)
    offset = (Part.makeBox(60, 20, 2)
              .fuse(Part.makeBox(10, 20, 2, v(0, 0, 2)))
              .fuse(Part.makeBox(10, 20, 6, v(40, 0, 2)))
              .fuse(Part.makeBox(20, 20, 2, v(20, 0, 6))).removeSplitter())
    offset_low = horizontal_face(offset, 4, 1)
    offset_high = horizontal_face(offset, 6, -1)
    cases = {
        "partial_forward": (stepped, [("large", large), ("small", small)]),
        "partial_reverse": (stepped, [("small", small), ("large", large)]),
        "full_order_a": (stepped, [("large", large), ("base_top", base_top), ("small", small)]),
        "full_order_b": (stepped, [("small", small), ("large", large), ("base_top", base_top)]),
        "ring": (ring, [("top", ring_top), ("bottom", ring_bottom)]),
        "air_gap": (open_gap, [("lower", gap_lower), ("upper", gap_upper)]),
        "no_overlap": (offset, [("low", offset_low), ("high", offset_high)]),
    }
    result = {}
    for name, (solid, faces) in cases.items():
        pairs, status = thin_wall_pair_evidence(solid, faces)
        result[name] = {"pairs": pairs, "status": status}
    Path(job["result_json_path"]).write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
