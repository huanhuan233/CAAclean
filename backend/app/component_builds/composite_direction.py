"""Nominal local direction from verified rosette and planar reference evidence."""

from __future__ import annotations

import math
from typing import Any


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def _unit(value):
    length = math.sqrt(_dot(value, value))
    return [x/length for x in value] if length > 1e-9 else None


def _field_number(fields: dict[str, Any], key: str) -> float | None:
    field = fields.get(key) or {}
    if field.get("read_status") != "available":
        return None
    try:
        value = float(field["raw_value"])
    except (ValueError, TypeError, KeyError):
        return None
    return value if math.isfinite(value) else None


def derive_nominal_planar_direction(row: dict[str, Any]) -> dict[str, Any]:
    result = {"status": "unavailable", "source": "derived_nominal_rosette_projection",
              "vector": None, "angle_deg": None, "normal": None,
              "handedness": None, "diagnostics": []}
    region = row.get("contour_planar_region") or {}
    plane = region.get("plane") or {}
    if region.get("status") != "derived_planar" or not isinstance(plane.get("normal"), list):
        result["diagnostics"].append("verified_planar_reference_missing")
        return result
    fields = row.get("fields") or {}
    angle = (fields.get("composite_orientation") or {}).get("normalized_value")
    if not isinstance(angle, (int, float)) or not math.isfinite(angle):
        result["diagnostics"].append("nominal_angle_unavailable")
        return result
    x = [_field_number(fields, f"composite_rosette_x_{axis}") for axis in "xyz"]
    y = [_field_number(fields, f"composite_rosette_y_{axis}") for axis in "xyz"]
    if any(value is None for value in x+y):
        result["diagnostics"].append("rosette_basis_unavailable")
        return result
    x = [float(value) for value in x]
    y = [float(value) for value in y]
    normal = [float(value) for value in plane["normal"]]
    if (len(normal) != 3 or not all(math.isfinite(value) for value in normal) or
        abs(math.sqrt(_dot(x, x))-1) > 1e-3 or abs(math.sqrt(_dot(y, y))-1) > 1e-3 or
        abs(_dot(x, y)) > 1e-3):
        result["diagnostics"].append("invalid_rosette_basis")
        return result
    n = _unit(normal)
    if n is None:
        result["diagnostics"].append("invalid_surface_normal")
        return result
    u = _unit([x[i]-_dot(x,n)*n[i] for i in range(3)])
    projected_y = _unit([y[i]-_dot(y,n)*n[i] for i in range(3)])
    if u is None or projected_y is None:
        result["diagnostics"].append("rosette_projection_degenerate")
        return result
    reference_v = _cross(n, u)
    handedness = _dot(projected_y, reference_v)
    if abs(handedness) < 1e-3:
        result["diagnostics"].append("rosette_handedness_undetermined")
        return result
    sign = 1 if handedness > 0 else -1
    radians = math.radians(angle)
    vector = [math.cos(radians)*u[i] + math.sin(radians)*sign*reference_v[i] for i in range(3)]
    result.update({"status": "derived_planar_nominal", "vector": vector, "normal": n,
                   "angle_deg": angle, "handedness": "aligned" if sign > 0 else "opposite",
                   "rule": "project_rosette_x_to_tangent_then_rotate_about_reference_normal",
                   "scope": "evaluated planar reference only; not a draped fiber path"})
    return result
