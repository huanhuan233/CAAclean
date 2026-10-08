"""Validate captured native face-boundary evidence without repairing source geometry."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def assess_native_boundaries(payload: Any, read_status: str) -> dict[str, Any]:
    """Return conservative lengths and roles; no polygon fill or projected area claim."""
    result: dict[str, Any] = {
        "status": "unavailable", "source": "native_face_boundary_iterator",
        "face_count": 0, "region_count": 0, "inner_loop_count": 0, "unknown_loop_count": 0,
        "raw_edge_occurrence_length_mm": None, "outer_boundary_length_mm": None,
        "inner_boundary_length_mm": None, "effective_boundary_length_mm": None,
        "area_mm2": None, "diagnostics": [],
    }
    if not isinstance(payload, dict) or not isinstance(payload.get("faces"), list):
        result["diagnostics"].append("native_boundary_payload_missing")
        return result
    faces = payload["faces"]
    result["face_count"] = len(faces)
    diagnostics: list[str] = result["diagnostics"]
    if read_status != "available":
        diagnostics.append(f"capture_read_status:{read_status}")
    expected = payload.get("expected_unique_edges")
    reported_unique = payload.get("visited_unique_edges")
    reported_occurrences = payload.get("visited_edge_occurrences")
    edge_counts: Counter[int] = Counter()
    raw_length = 0.0
    outer_length = 0.0
    inner_length = 0.0
    observed_occurrences = 0
    for face in faces:
        if not isinstance(face, dict) or not isinstance(face.get("loops"), list):
            diagnostics.append("invalid_face_record")
            continue
        for loop in face["loops"]:
            if not isinstance(loop, dict) or not isinstance(loop.get("edges"), list) or not loop["edges"]:
                diagnostics.append("empty_or_invalid_loop")
                continue
            role = loop.get("location")
            if role == "outer":
                result["region_count"] += 1
            elif role == "inner":
                result["inner_loop_count"] += 1
            else:
                result["unknown_loop_count"] += 1
            for edge in loop["edges"]:
                observed_occurrences += 1
                if not isinstance(edge, dict):
                    diagnostics.append("invalid_edge_record")
                    continue
                edge_index = edge.get("edge_index")
                length = _number(edge.get("length_mm"))
                if not isinstance(edge_index, int) or edge_index <= 0 or length is None or length < 0:
                    diagnostics.append("invalid_edge_measurement")
                    continue
                edge_counts[edge_index] += 1
                raw_length += length
                if role == "outer":
                    outer_length += length
                elif role == "inner":
                    inner_length += length
    if not all(isinstance(value, int) and value >= 0 for value in (expected, reported_unique, reported_occurrences)):
        diagnostics.append("edge_counts_missing")
    elif expected != reported_unique or reported_unique != len(edge_counts) or reported_occurrences != observed_occurrences:
        diagnostics.append("edge_visit_incomplete")
    if not faces:
        diagnostics.append("no_surface_faces")
    repeated = any(count > 1 for count in edge_counts.values())
    if repeated:
        diagnostics.append("shared_or_seam_edge_occurrence")
    result["raw_edge_occurrence_length_mm"] = raw_length if observed_occurrences and "invalid_edge_measurement" not in diagnostics else None
    hard_failure = any(code in diagnostics for code in (
        "invalid_face_record", "empty_or_invalid_loop", "invalid_edge_record",
        "invalid_edge_measurement", "edge_counts_missing", "edge_visit_incomplete", "no_surface_faces",
    )) or read_status != "available"
    if hard_failure:
        result["status"] = "partial"
    elif repeated or result["unknown_loop_count"]:
        result["status"] = "needs_review"
    else:
        result["status"] = "complete"
        result["outer_boundary_length_mm"] = outer_length
        result["inner_boundary_length_mm"] = inner_length
        result["effective_boundary_length_mm"] = outer_length + inner_length
    return result
