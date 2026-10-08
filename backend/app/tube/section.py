"""Interpret a captured native sweep sketch without claiming measured tube walls."""

from __future__ import annotations

import math
from typing import Any


def native_concentric_profile(sketch: dict[str, Any], tolerance_mm: float = 0.001) -> dict[str, Any]:
    """Return design profile dimensions only for two full concentric circles."""
    unknown = {"status": "unsupported_profile", "source": "native_sketch", "outer_diameter_mm": None,
               "inner_diameter_mm": None, "nominal_wall_mm": None}
    if sketch.get("axis", {}).get("status") != "verified_orthonormal":
        return unknown
    elements = sketch.get("elements") or []
    relevant = [item for item in elements if item.get("construction") is False]
    if len(relevant) != 2 or any(item.get("kind") != "circle" for item in relevant):
        return unknown
    circles = []
    for item in relevant:
        center = item.get("center_2d_mm")
        limits = item.get("parameter_range_raw")
        radius = item.get("radius_mm")
        if (not isinstance(center, list) or len(center) != 2 or
            not isinstance(limits, list) or len(limits) != 2 or
            isinstance(radius, bool) or not isinstance(radius, (int, float))):
            return unknown
        try:
            cx, cy = map(float, center)
            start, end = map(float, limits)
            radius = float(radius)
        except (ValueError, TypeError):
            return unknown
        if not all(map(math.isfinite, (cx, cy, start, end, radius))) or radius <= tolerance_mm:
            return unknown
        if abs(abs(end - start) - 2 * math.pi) > 1e-4:
            return unknown
        circles.append((radius, cx, cy, str(item.get("element_id") or "")))
    outer, inner = sorted(circles, reverse=True)
    if (outer[0] - inner[0] <= tolerance_mm or
        math.hypot(outer[1] - inner[1], outer[2] - inner[2]) > tolerance_mm or
        not outer[3] or not inner[3]):
        return unknown
    return {"status": "native_profile_annulus", "source": "native_sketch",
            "outer_diameter_mm": 2 * outer[0], "inner_diameter_mm": 2 * inner[0],
            "nominal_wall_mm": outer[0] - inner[0], "center_2d_mm": [outer[1], outer[2]],
            "element_ids": [outer[3], inner[3]], "unit": "mm",
            "scope": "sweep_input_sketch_only;solid_wall_unverified"}
