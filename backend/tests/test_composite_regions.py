import math

from app.component_builds.composite_regions import derive_planar_regions


def _loop(points, first_index, location="unknown"):
    edges = []
    for i, point in enumerate(points):
        end = points[(i + 1) % len(points)]
        edges.append({"edge_index": first_index + i, "curve_type": "line",
                      "start_mm": [*point, 0], "end_mm": [*end, 0],
                      "length_mm": math.dist(point, end), "orientation": "positive"})
    return {"domain_index": first_index, "location": location, "edges": edges}


def _payload(*loops):
    edges = [edge for loop in loops for edge in loop["edges"]]
    return {"source": "CATBody.GetDomain/CATDomain.GetCell", "faces": [
        {"face_index": 0, "loops": list(loops)}],
        "expected_unique_edges": len(edges), "visited_unique_edges": len(edges),
        "visited_edge_occurrences": len(edges)}


def test_planar_outer_hole_and_disjoint_outer_are_classified_by_containment():
    outer = _loop([(0, 0), (10, 0), (10, 10), (0, 10)], 1)
    hole = _loop([(2, 2), (2, 4), (4, 4), (4, 2)], 5)
    other = _loop([(20, 0), (25, 0), (25, 5), (20, 5)], 9)
    result = derive_planar_regions(_payload(outer, hole, other))
    assert result["status"] == "derived_planar"
    assert result["region_count"] == 2
    assert result["hole_count"] == 1
    assert math.isclose(result["area_mm2"], 121)
    assert result["area_error_bound_mm2"] == 0
    assert [loop["role"] for loop in result["loops"]] == ["outer", "inner", "outer"]


def test_reversed_edge_uses_still_close_without_reordering_native_members():
    loop = _loop([(0, 0), (10, 0), (10, 10), (0, 10)], 1)
    loop["edges"][1]["start_mm"], loop["edges"][1]["end_mm"] = (
        loop["edges"][1]["end_mm"], loop["edges"][1]["start_mm"])
    result = derive_planar_regions(_payload(loop))
    assert result["status"] == "derived_planar"
    assert math.isclose(result["area_mm2"], 100)
    assert result["loops"][0]["edge_indices"] == [1, 2, 3, 4]


def test_gap_or_bow_tie_is_not_repaired_into_area():
    open_loop = _loop([(0, 0), (10, 0), (10, 10), (0, 10)], 1)
    open_loop["edges"][2]["start_mm"] = [10.1, 10, 0]
    assert derive_planar_regions(_payload(open_loop))["status"] == "unsupported"
    bow_tie = _loop([(0, 0), (10, 10), (0, 10), (10, 0)], 1)
    assert derive_planar_regions(_payload(bow_tie))["status"] == "unsupported"


def test_circle_supports_arc_sampling_with_error_bound_and_true_native_length():
    circle = {"domain_index": 1, "location": "unknown", "edges": [{
        "edge_index": 1, "curve_type": "circle", "radius_mm": 10,
        "center_mm": [0, 0, 0], "axis_u": [1, 0, 0], "axis_v": [0, 1, 0],
        "curve_start_param": 0, "curve_end_param": 2 * math.pi,
        "start_mm": None, "end_mm": None, "length_mm": 20 * math.pi,
    }]}
    result = derive_planar_regions(_payload(circle))
    assert result["status"] == "derived_planar"
    assert abs(result["area_mm2"] - 100 * math.pi) < result["area_error_bound_mm2"]
    assert math.isclose(result["outer_boundary_length_mm"], 20 * math.pi)
    assert result["display_sampling_error_mm"] <= 0.05
