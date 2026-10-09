"""Finite planar curve measurements; all values remain in drawing units."""

from __future__ import annotations

import math

UNIT_TO_MM = {1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0,
              7: 1_000_000.0, 8: 0.0000254, 9: 0.0254, 10: 914.4,
              11: 1.0e-7, 12: 1.0e-6, 13: 0.001, 14: 100.0}


def _segment(a: list[float], b: list[float], bulge: float) -> tuple[float, float]:
    chord = math.hypot(b[0] - a[0], b[1] - a[1])
    cross = (a[0] * b[1] - b[0] * a[1]) / 2
    if not bulge or chord == 0:
        return chord, cross
    angle = 4 * math.atan(bulge)
    radius = chord * (1 + bulge * bulge) / (4 * abs(bulge))
    return abs(angle) * radius, cross + radius * radius * (angle - math.sin(angle)) / 2


def _intersection(a, b, c, d) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    x1, x2 = orient(a, b, c), orient(a, b, d)
    y1, y2 = orient(c, d, a), orient(c, d, b)
    return x1 * x2 < -1e-12 and y1 * y2 < -1e-12


def measure_entity(record: dict, unit_code: int) -> dict:
    """Return a new JSON-safe record; undefined area has an explicit reason."""
    result = dict(record)
    if record.get("status"):
        return result
    kind = record["type"]
    length = None
    area = None
    reason = "not_applicable"
    if kind == "LINE":
        length = math.dist(record["start"], record["end"])
    elif kind == "CIRCLE":
        length = 2 * math.pi * record["radius"]
        area = math.pi * record["radius"] ** 2
        reason = None
    elif kind == "ARC":
        sweep = (record["end_angle"] - record["start_angle"]) % 360
        length = math.radians(sweep) * record["radius"]
    elif kind in {"LWPOLYLINE", "POLYLINE"}:
        vertices = record["vertices"]
        closed = record["closed"]
        pairs = [(index, (index + 1) % len(vertices)) for index in range(len(vertices) if closed else len(vertices) - 1)]
        length = 0.0
        signed_area = 0.0
        for start, end in pairs:
            segment_length, segment_area = _segment(vertices[start], vertices[end], vertices[start][4])
            length += segment_length
            signed_area += segment_area
        if closed and len(vertices) >= 3:
            # Non-adjacent straight segments are checked before publishing an area.
            crossings = any(_intersection(vertices[a], vertices[b], vertices[c], vertices[d])
                            for i, (a, b) in enumerate(pairs) for j, (c, d) in enumerate(pairs)
                            if j > i + 1 and not (i == 0 and j == len(pairs) - 1))
            if crossings:
                reason = "self_intersection"
            else:
                area = abs(signed_area)
                reason = None
        elif closed:
            reason = "insufficient_vertices"
        else:
            reason = "open_contour"
    result["length"] = length
    result["single_contour_area"] = area
    result["area_undefined_reason"] = reason
    scale = UNIT_TO_MM.get(unit_code)
    result["normalized"] = {"length_mm": length * scale if length is not None and scale else None,
                            "single_contour_area_mm2": area * scale * scale if area is not None and scale else None,
                            "unit_status": "known" if scale else "drawing_unit"}
    return result
