import math

from app.component_builds.composite_boundaries import assess_native_boundaries


def _edge(index, length, start=None, end=None, curve_type="line"):
    return {"edge_index": index, "length_mm": length, "start_mm": start, "end_mm": end,
            "curve_type": curve_type, "orientation": "positive", "trim_start": 0, "trim_end": 1}


def _square(index_start, x0, y0, x1, y1, location="outer"):
    points = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]
    edges = [_edge(index_start + n, math.dist(points[n], points[(n+1) % 4]),
                   points[n], points[(n+1) % 4]) for n in range(4)]
    return {"domain_index": index_start, "location": location, "edges": edges}


def test_native_outer_hole_and_two_regions_preserve_loop_roles_and_perimeter():
    payload = {"expected_unique_edges": 9, "visited_unique_edges": 9,
               "visited_edge_occurrences": 9, "faces": [{"face_index": 1, "loops": [
                   _square(1, 0, 0, 10, 10),
                   {"domain_index": 2, "location": "inner", "edges": [
                       _edge(5, 2 * math.pi * 2, curve_type="circle")]},
                   _square(6, 20, 0, 25, 5),
               ]}]}
    result = assess_native_boundaries(payload, "available")
    assert result["status"] == "complete"
    assert result["region_count"] == 2
    assert result["inner_loop_count"] == 1
    assert math.isclose(result["outer_boundary_length_mm"], 60)
    assert math.isclose(result["inner_boundary_length_mm"], 4 * math.pi)
    assert result["area_mm2"] is None  # A boundary alone does not establish a curved surface area.


def test_partial_traversal_cannot_claim_complete_boundary_or_effective_length():
    payload = {"expected_unique_edges": 5, "visited_unique_edges": 4,
               "visited_edge_occurrences": 4, "faces": [{"face_index": 1, "loops": [
                   _square(1, 0, 0, 10, 10)]}]}
    result = assess_native_boundaries(payload, "available")
    assert result["status"] == "partial"
    assert result["effective_boundary_length_mm"] is None
    assert "edge_visit_incomplete" in result["diagnostics"]


def test_multiface_shared_edge_and_periodic_seam_do_not_inflate_perimeter():
    payload = {"expected_unique_edges": 1, "visited_unique_edges": 1,
               "visited_edge_occurrences": 2, "faces": [
                   {"face_index": 1, "loops": [{"domain_index": 1, "location": "outer", "edges": [_edge(1, 10)]}]},
                   {"face_index": 2, "loops": [{"domain_index": 1, "location": "outer", "edges": [_edge(1, 10)]}]},
               ]}
    result = assess_native_boundaries(payload, "available")
    assert result["status"] == "needs_review"
    assert result["raw_edge_occurrence_length_mm"] == 20
    assert result["effective_boundary_length_mm"] is None


def test_invalid_or_unknown_native_roles_remain_unclassified():
    payload = {"expected_unique_edges": 1, "visited_unique_edges": 1,
               "visited_edge_occurrences": 1, "faces": [{"face_index": 1, "loops": [
                   {"domain_index": 1, "location": "unknown", "edges": [_edge(1, 5)]}]}]}
    result = assess_native_boundaries(payload, "partial")
    assert result["status"] == "partial"
    assert result["outer_boundary_length_mm"] is None
    assert result["inner_boundary_length_mm"] is None
