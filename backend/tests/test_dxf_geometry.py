import math

import pytest

from app.dxf.geometry import measure_entity


def polyline(vertices, closed=True):
    return {"type": "LWPOLYLINE", "vertices": vertices, "closed": closed}


def test_positive_and_negative_bulge_keep_signed_arc_area():
    positive = measure_entity(polyline([[0, 0, 0, 0, 1], [2, 0, 0, 0, 0]]), 4)
    negative = measure_entity(polyline([[0, 0, 0, 0, -1], [2, 0, 0, 0, 0]]), 4)
    assert positive["length"] == pytest.approx(math.pi + 2)
    assert negative["length"] == pytest.approx(math.pi + 2)
    assert positive["single_contour_area"] == pytest.approx(math.pi / 2)
    assert negative["single_contour_area"] == pytest.approx(math.pi / 2)


def test_last_closing_segment_bulge_and_major_arc():
    result = measure_entity(polyline([[0, 0, 0, 0, 0], [2, 0, 0, 0, 2]]), 4)
    assert result["length"] > 2 + math.pi
    assert result["single_contour_area"] is not None


def test_open_self_intersection_and_unknown_units_are_distinct():
    open_line = measure_entity(polyline([[0, 0, 0, 0, 0], [2, 0, 0, 0, 0]], False), 0)
    crossing = measure_entity(polyline([[0, 0, 0, 0, 0], [2, 2, 0, 0, 0],
                                        [0, 2, 0, 0, 0], [2, 0, 0, 0, 0]]), 4)
    assert open_line["area_undefined_reason"] == "open_contour"
    assert open_line["normalized"]["length_mm"] is None
    assert crossing["area_undefined_reason"] == "self_intersection"
    assert crossing["single_contour_area"] is None
