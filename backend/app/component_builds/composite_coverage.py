"""Same-reference planar ply coverage and nominal thickness.

Only native ply identity/order and previously verified contour regions enter this
module. FreeCAD computes all booleans in one isolated job; missing data remains
unknown and cannot be interpreted as zero coverage or zero thickness.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


ALGORITHM = "composite_planar_coverage_v1"
MAX_PLIES = 64


def _field_value(row: dict[str, Any], key: str) -> Any:
    field = row.get("fields", {}).get(key) or {}
    return field.get("raw_value") if field.get("read_status") == "available" else None


def prepare_planar_coverage(rows: list[dict[str, Any]], group_id: str,
                            thickness_basis: str) -> dict[str, Any]:
    if thickness_basis not in {"cured", "uncured"}:
        raise ValueError("thickness basis must be cured or uncured")
    by_id = {row["object_id"]: row for row in rows if row.get("object_id")}
    if len(by_id) != len(rows):
        raise ValueError("duplicate or missing composite object identity")
    group = by_id.get(group_id)
    if not group or group.get("kind") != "group":
        raise ValueError("composite group not found")
    order_complete = group.get("order_status") == "native_complete"
    sequence_ids = (group.get("ordered_child_object_ids") or []) if order_complete else sorted(
        row["object_id"] for row in rows
        if row.get("kind") == "sequence" and group_id in (row.get("parent_object_ids") or [])
    )
    ply_ids: list[str] = []
    for sequence_id in sequence_ids:
        sequence = by_id.get(sequence_id)
        if not sequence or sequence.get("kind") != "sequence":
            raise ValueError("group sequence identity is unresolved")
        sequence_order_complete = sequence.get("order_status") == "native_complete"
        order_complete = order_complete and sequence_order_complete
        sequence_ply_ids = (sequence.get("ordered_child_object_ids") or []) if sequence_order_complete else sorted(
            row["object_id"] for row in rows
            if row.get("kind") == "ply" and sequence_id in (row.get("parent_object_ids") or [])
        )
        for ply_id in sequence_ply_ids:
            ply = by_id.get(ply_id)
            if not ply or ply.get("kind") != "ply":
                raise ValueError("ply identity is unresolved")
            ply_ids.append(ply_id)
    if not ply_ids or len(ply_ids) > MAX_PLIES or len(set(ply_ids)) != len(ply_ids):
        raise ValueError("ply count or identity invalid")
    plies = [by_id[ply_id] for ply_id in ply_ids]
    reference_ids = {_field_value(ply, "composite_reference_surface_object_id") for ply in plies}
    if len(reference_ids) != 1 or None in reference_ids or "" in reference_ids:
        raise ValueError("common native reference surface not established")
    document_ids = {ply.get("document_id") for ply in plies}
    if len(document_ids) != 1 or None in document_ids:
        raise ValueError("ply document identity mismatch")
    normal = None
    origin = None
    kernel_plies = []
    for ply in plies:
        region = ply.get("contour_planar_region") or {}
        if region.get("status") != "derived_planar" or not region.get("loops"):
            raise ValueError(f"verified planar contour missing: {ply['object_id']}")
        plane = region.get("plane") or {}
        try:
            current_normal = [float(value) for value in plane["normal"]]
            current_origin = [float(value) for value in plane["origin_mm"]]
        except (KeyError, TypeError, ValueError):
            raise ValueError("planar contour reference frame missing") from None
        if len(current_normal) != 3 or len(current_origin) != 3 or not all(
            math.isfinite(value) for value in current_normal + current_origin
        ):
            raise ValueError("invalid planar reference frame")
        if normal is None:
            normal, origin = current_normal, current_origin
        elif abs(sum(a*b for a, b in zip(normal, current_normal))) < 1 - 1e-6 or abs(
            sum(a*(b-c) for a, b, c in zip(normal, current_origin, origin))
        ) > 1e-4:
            raise ValueError("ply contours are not on the same verified plane")
        kernel_plies.append({"object_id": ply["object_id"], "loops": region["loops"]})
    return {
        "group_object_id": group_id, "reference_surface_object_id": next(iter(reference_ids)),
        "document_id": next(iter(document_ids)), "ply_object_ids": ply_ids,
        "ordered_ply_object_ids": ply_ids if order_complete else None,
        "layer_order_status": "native_complete" if order_complete else "unavailable",
        "thickness_basis": thickness_basis, "plies": kernel_plies,
    }


def add_nominal_thickness(kernel_result: dict[str, Any], prepared: dict[str, Any],
                          rows: list[dict[str, Any]], revision_id: str,
                          geometry_snapshot_id: str | None = None) -> dict[str, Any]:
    if kernel_result.get("status") != "computed":
        raise ValueError(f"coverage kernel result is not computed: {kernel_result.get('status')}")
    by_id = {row["object_id"]: row for row in rows}
    thickness_key = f"composite_{prepared['thickness_basis']}_thickness"
    cells = []
    for number, cell in enumerate(kernel_result.get("cells") or [], 1):
        ids = cell.get("ply_object_ids") or []
        area = cell.get("area_mm2")
        if (not ids or len(set(ids)) != len(ids) or
            any(ply_id not in prepared["ply_object_ids"] for ply_id in ids) or
            not isinstance(area, (int, float)) or not math.isfinite(area) or area <= 0):
            raise ValueError("coverage kernel returned unknown ply identity")
        known = 0.0
        missing = []
        contributions = []
        for ply_id in ids:
            field = (by_id[ply_id].get("fields") or {}).get(thickness_key) or {}
            value = field.get("normalized_value")
            if field.get("read_status") != "available" or field.get("normalized_unit") != "mm" or not isinstance(
                value, (int, float)
            ) or not math.isfinite(value) or value < 0:
                missing.append(ply_id)
                contributions.append({"ply_object_id": ply_id, "thickness_mm": None,
                                      "source_property_id": field.get("property_id"), "status": "unknown"})
            else:
                known += value
                contributions.append({"ply_object_id": ply_id, "thickness_mm": value,
                                      "source_property_id": field.get("property_id"), "status": "available"})
        cells.append({**cell, "region_id": f"region_{number}", "layer_count": len(ids),
                      "known_thickness_subtotal_mm": known,
                      "nominal_thickness_mm": None if missing else known,
                      "thickness_status": "incomplete" if missing else "complete",
                      "unknown_thickness_ply_object_ids": missing,
                      "contributions": contributions})
    for ply_id in prepared["ply_object_ids"]:
        region = by_id[ply_id]["contour_planar_region"]
        measured = sum(cell["area_mm2"] for cell in cells if ply_id in cell["ply_object_ids"])
        expected = float(region["area_mm2"])
        allowed = max(1e-3, float(region.get("area_error_bound_mm2") or 0) + expected*1e-6)
        if abs(measured - expected) > allowed:
            raise ValueError(f"coverage area conservation failed: {ply_id}")
    source = {
        "algorithm": ALGORITHM, "revision_id": revision_id,
        "geometry_snapshot_id": geometry_snapshot_id,
        "document_id": prepared["document_id"],
        "group_object_id": prepared["group_object_id"],
        "reference_surface_object_id": prepared["reference_surface_object_id"],
        "layer_order_status": prepared["layer_order_status"],
        "ply_object_ids": prepared["ply_object_ids"],
        "ordered_ply_object_ids": prepared["ordered_ply_object_ids"],
        "thickness_basis": prepared["thickness_basis"],
        "group_reference_and_rosette": {
            key: field for key, field in (by_id[prepared["group_object_id"]].get("fields") or {}).items()
            if key.startswith("composite_rosette_") or key.startswith("composite_reference_surface")
        },
        "source_regions_and_fields": [{"id": ply_id,
            "region": by_id[ply_id].get("contour_planar_region"),
            "thickness": (by_id[ply_id].get("fields") or {}).get(thickness_key),
            "orientation": (by_id[ply_id].get("fields") or {}).get("composite_orientation"),
            "nominal_direction": by_id[ply_id].get("nominal_direction")}
            for ply_id in prepared["ply_object_ids"]],
    }
    fingerprint = hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"object_id": prepared["group_object_id"], "status": "computed",
            "algorithm": ALGORITHM, "source_fingerprint": fingerprint,
            "revision_id": revision_id, "geometry_snapshot_id": geometry_snapshot_id,
            "document_id": prepared["document_id"],
            "reference_surface_object_id": prepared["reference_surface_object_id"],
            "layer_order_status": prepared["layer_order_status"],
            "ply_object_ids": prepared["ply_object_ids"],
            "ordered_ply_object_ids": prepared["ordered_ply_object_ids"],
            "thickness_basis": prepared["thickness_basis"], "cells": cells,
            "transitions": kernel_result.get("transitions") or [],
            "transition_status": kernel_result.get("transition_status"),
            "geometry_method": kernel_result.get("method"),
            "freecad_version": kernel_result.get("freecad_version"),
            "kernel_version": kernel_result.get("kernel_version"),
            "display_sampling_error_mm": 0.05,
            "limits": "verified same-plane contours only; display geometry sampled from native curves"}


async def compute_planar_coverage(rows: list[dict[str, Any]], group_id: str,
                                  thickness_basis: str, revision_id: str,
                                  geometry_snapshot_id: str | None, settings: Settings,
                                  work_dir: Path) -> dict[str, Any]:
    prepared = prepare_planar_coverage(rows, group_id, thickness_basis)
    script = Path(settings.cad_script_dir) / "composite_overlay.py"
    kernel = await run_freecad_job(script, {"plies": prepared["plies"]}, work_dir, settings)
    return add_nominal_thickness(kernel, prepared, rows, revision_id, geometry_snapshot_id)


def coverage_at_point(result: dict[str, Any], point_mm: tuple[float, float, float],
                      tolerance_mm: float = 0.01) -> dict[str, Any]:
    """Query only published sampled planar regions; boundaries remain ambiguous."""
    if len(point_mm) != 3 or not all(math.isfinite(value) for value in point_mm):
        raise ValueError("finite 3D point required")
    if not 0 < tolerance_mm <= 0.1:
        raise ValueError("invalid point query tolerance")
    hits = []
    for cell in result.get("cells") or []:
        vertices = cell.get("display_vertices_mm") or []
        for triangle in cell.get("display_triangles") or []:
            if len(triangle) != 3 or any(index >= len(vertices) for index in triangle):
                continue
            a, b, c = (vertices[index] for index in triangle)
            ab = [b[i]-a[i] for i in range(3)]
            ac = [c[i]-a[i] for i in range(3)]
            ap = [point_mm[i]-a[i] for i in range(3)]
            normal = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
            length = math.sqrt(sum(value*value for value in normal))
            if length <= 1e-12 or abs(sum(ap[i]*normal[i] for i in range(3)) / length) > tolerance_mm:
                continue
            d00 = sum(value*value for value in ab)
            d01 = sum(ab[i]*ac[i] for i in range(3))
            d11 = sum(value*value for value in ac)
            d20 = sum(ap[i]*ab[i] for i in range(3))
            d21 = sum(ap[i]*ac[i] for i in range(3))
            denom = d00*d11-d01*d01
            if denom <= 1e-18:
                continue
            v = (d11*d20-d01*d21)/denom
            w = (d00*d21-d01*d20)/denom
            u = 1-v-w
            edge_fraction = tolerance_mm / max(math.sqrt(d00), math.sqrt(d11), 1e-6)
            if min(u, v, w) >= -edge_fraction:
                hits.append(cell)
                break
    if not hits:
        return {"status": "outside_computed_regions", "point_mm": list(point_mm),
                "ply_object_ids": None, "nominal_thickness_mm": None}
    unique = {cell["region_id"]: cell for cell in hits}
    if len(unique) != 1 or _on_cell_boundary(next(iter(unique.values())), point_mm, tolerance_mm):
        return {"status": "boundary_ambiguous", "point_mm": list(point_mm),
                "region_ids": list(unique), "ply_object_ids": None,
                "nominal_thickness_mm": None}
    cell = next(iter(unique.values()))
    return {"status": "inside_computed_region", "point_mm": list(point_mm),
            "region_id": cell["region_id"], "ply_object_ids": cell["ply_object_ids"],
            "nominal_thickness_mm": cell["nominal_thickness_mm"],
            "thickness_status": cell["thickness_status"],
            "reference_surface_object_id": result.get("reference_surface_object_id"),
            "revision_id": result.get("revision_id")}


def _on_cell_boundary(cell: dict[str, Any], point: tuple[float, float, float], tolerance: float) -> bool:
    counts: dict[tuple[int, int], int] = {}
    for a, b, c in cell.get("display_triangles") or []:
        for pair in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(pair))
            counts[key] = counts.get(key, 0) + 1
    vertices = cell.get("display_vertices_mm") or []
    for (start, end), count in counts.items():
        if count != 1:
            continue
        a, b = vertices[start], vertices[end]
        direction = [b[i]-a[i] for i in range(3)]
        length_squared = sum(value*value for value in direction)
        if length_squared <= 1e-18:
            continue
        fraction = max(0.0, min(1.0, sum((point[i]-a[i])*direction[i] for i in range(3))/length_squared))
        if math.sqrt(sum((point[i]-a[i]-fraction*direction[i])**2 for i in range(3))) <= tolerance:
            return True
    return False
