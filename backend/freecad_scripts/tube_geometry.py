"""Analytic straight/bent hollow tube recognition in one loaded B-Rep task.

Circular inner/outer walls, finite topology, material and sections must agree.
This script never infers a CATIA feature or a manufacturing process.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import FreeCAD
import Part

from measure_geometry import GeometryKernelContext, xyz
from assembly_relations import evaluate_pair
from tube_sections import classify_analytic_tube, centerline_station

CONFIRMED_TUBE_STATUSES = {"confirmed_straight_hollow_tube", "confirmed_bent_hollow_tube"}


MAX_SOLIDS = 32
MAX_FACES = 256


def run(job):
    items = job.get("solids") or []
    tolerance = float(job.get("tolerance_mm", 0.01))
    if not 1 <= len(items) <= MAX_SOLIDS or not math.isfinite(tolerance) or not 0 < tolerance <= 0.1:
        raise ValueError("invalid_input: solid count or tolerance")
    if any(not item.get("solid_id") or not item.get("asset_path") for item in items):
        raise ValueError("invalid_input: solid identity and asset required")
    if len({item["solid_id"] for item in items}) != len(items):
        raise ValueError("invalid_input: duplicate solid identity")
    coordinate_system = job.get("coordinate_system", "step_world")
    if coordinate_system != "step_world":
        raise ValueError("invalid_input: unsupported coordinate system")
    context = GeometryKernelContext([item["asset_path"] for item in items], ["solid"] * len(items), tolerance)
    started = time.perf_counter()
    records = []
    for item, solid in zip(items, context.shapes):
        if len(solid.Faces) > MAX_FACES:
            records.append({"solid_id": item["solid_id"], "status": "analysis_budget_exceeded",
                            "source": "derived_geometry", "unmet_conditions": ["face_count_over_256"]})
        else:
            records.append({"solid_id": item["solid_id"], **classify_analytic_tube(solid, tolerance, coordinate_system)})
    clearances = []
    target_id = job.get("target_tube_solid_id")
    if target_id is not None:
        matches = [index for index, item in enumerate(items) if item["solid_id"] == target_id]
        if len(matches) != 1 or records[matches[0]]["status"] not in CONFIRMED_TUBE_STATUSES:
            raise ValueError("unsupported: target is not one verified analytic hollow tube")
        target_index = matches[0]
        tube = context.shapes[target_index]
        record = records[target_index]
        exterior = Part.makeCompound([tube.Faces[i - 1] for i in record["exterior_face_indices"]])
        path = record["path"]
        for index, item in enumerate(items):
            if index == target_index:
                continue
            neighbor = context.shapes[index]
            pair = evaluate_pair(tube, neighbor, tolerance)
            try:
                distance, witnesses, _ = exterior.distToShape(neighbor)
                if not math.isfinite(distance) or not witnesses:
                    raise ValueError("finite exterior witness unavailable")
                actual = []
                for a, b in witnesses[:16]:
                    station, station_status = centerline_station(path, a, tolerance)
                    actual.append({"tube": xyz(a), "target": xyz(b), "s_mm": station,
                                   "station_status": station_status})
                status = "evaluated" if pair.get("status") == "evaluated" else "partial"
                if distance > tolerance and pair.get("distance_mm", 0) <= tolerance:
                    status = "partial"
                clearances.append({"tube_solid_id": target_id, "target_solid_id": item["solid_id"],
                                   "status": status, "distance_mm": float(distance),
                                   "within_tolerance": bool(distance <= tolerance),
                                   "witnesses": actual, "solution_count": len(witnesses),
                                   "intersection_status": pair.get("intersection_status", "not_evaluated"),
                                   "contact_kind": pair.get("contact_kind", "unknown"),
                                   "method": "exact_exterior_faces_to_target_solid",
                                   "scope": "all_verified_outer_walls_and_two_annular_ends",
                                   "threshold_status": "not_provided"})
            except Exception as exc:
                clearances.append({"tube_solid_id": target_id, "target_solid_id": item["solid_id"],
                                   "status": "failed", "diagnostic": type(exc).__name__,
                                   "distance_mm": None, "intersection_status": pair.get("intersection_status", "not_evaluated")})
    return {"status": "success", "records": records, "clearances": clearances,
            "algorithm_version": "tube.geometry.circular.v3",
            "diagnostics": {"loaded_shapes": context.loaded_shapes, "load_ms": context.load_ms,
                            "compute_ms": round((time.perf_counter() - started) * 1000, 3)},
            "kernel": "OpenCascade", "kernel_version": str(getattr(Part, "OCC_VERSION", "unknown") or "unknown"),
            "freecad_version": ".".join(str(value) for value in FreeCAD.Version()[:3])}


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(job)
    except ValueError as exc:
        result = {"status": "invalid_input", "diagnostic": str(exc)}
    except Exception as exc:
        result = {"status": "failed", "diagnostic": type(exc).__name__ + ": " + str(exc)}
    Path(job["result_json_path"]).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
