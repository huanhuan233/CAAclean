"""Explicit two-operand derived B-Rep; inputs are copied and never overwritten."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import FreeCAD
import Part


def run(job):
    operation = job["operation"]
    if operation not in {"union", "intersection", "difference"}:
        raise ValueError("invalid_input: unknown boolean operation")
    left = Part.Shape()
    right = Part.Shape()
    left.read(job["left_asset_path"])
    right.read(job["right_asset_path"])
    if any(shape.isNull() or not shape.isValid() or not shape.isClosed() or len(shape.Solids) != 1
           for shape in (left, right)):
        raise ValueError("invalid_input: both operands must be closed valid single solids")
    if operation == "union":
        derived = left.copy().fuse(right.copy())
    elif operation == "intersection":
        derived = left.copy().common(right.copy())
    else:
        derived = left.copy().cut(right.copy())
    if derived.isNull() or not derived.Solids or derived.Volume <= 0:
        return {"status": "empty", "operation": operation, "volume_mm3": 0.0,
                "asset": None, "source": "auxiliary_brep"}
    if not derived.isValid():
        raise ValueError("geometry_invalid: derived B-Rep failed validity check")
    output = Path(job["output_asset_path"])
    derived.exportBrep(str(output))
    raw = output.read_bytes()
    box = derived.BoundBox
    return {"status": "complete", "operation": operation, "volume_mm3": float(derived.Volume),
            "area_mm2": float(derived.Area),
            "bounds_mm": [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax],
            "asset": {"sha256": hashlib.sha256(raw).hexdigest(), "byte_size": len(raw)},
            "source": "auxiliary_brep", "kernel_version": str(getattr(Part, "OCC_VERSION", "unknown") or "unknown"),
            "freecad_version": ".".join(str(value) for value in FreeCAD.Version()[:3])}


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(job)
    except ValueError as exc:
        code, _, message = str(exc).partition(":")
        result = {"status": code or "failed", "diagnostic": message.strip() or str(exc)}
    except Exception as exc:
        result = {"status": "failed", "diagnostic": type(exc).__name__ + ": " + str(exc)}
    Path(job["result_json_path"]).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
