import asyncio
import math
import os
from pathlib import Path

import pytest

from app.component_builds.composite_coverage import (
    add_nominal_thickness, compute_planar_coverage, coverage_at_point, prepare_planar_coverage,
)
from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


def _region(x1, y1, x2, y2):
    points = [[x1, y1, 0], [x2, y1, 0], [x2, y2, 0], [x1, y2, 0]]
    return {"status": "derived_planar", "area_mm2": (x2-x1)*(y2-y1),
            "area_error_bound_mm2": 0, "plane": {"origin_mm": points[0], "normal": [0, 0, 1]},
            "loops": [{"role": "outer", "sampled_points_mm": points}]}


def _rows(second_region=None, second_thickness=0.3):
    second_region = second_region or _region(0, 0, 50, 100)
    return [
        {"object_id": "group", "kind": "group", "order_status": "native_complete",
         "ordered_child_object_ids": ["s1", "s2"]},
        {"object_id": "s1", "kind": "sequence", "order_status": "native_complete",
         "ordered_child_object_ids": ["A"]},
        {"object_id": "s2", "kind": "sequence", "order_status": "native_complete",
         "ordered_child_object_ids": ["B"]},
        *[{
            "object_id": ply_id, "kind": "ply", "document_id": "doc",
            "contour_planar_region": region,
            "fields": {
                "composite_reference_surface_object_id": {"read_status": "available", "raw_value": "surface"},
                "composite_cured_thickness": {"read_status": "available" if thickness is not None else "unavailable",
                                               "normalized_value": thickness, "normalized_unit": "mm",
                                               "property_id": f"thickness-{ply_id}"},
                "composite_uncured_thickness": {"read_status": "unavailable", "normalized_value": None},
            },
        } for ply_id, region, thickness in (
            ("A", _region(0, 0, 100, 100), 0.2), ("B", second_region, second_thickness))],
    ]


def test_thickness_basis_and_missing_value_are_not_silently_filled():
    rows = _rows(second_thickness=None)
    prepared = prepare_planar_coverage(rows, "group", "cured")
    kernel = {"status": "computed", "cells": [
        {"ply_object_ids": ["A"], "area_mm2": 5000},
        {"ply_object_ids": ["A", "B"], "area_mm2": 5000}], "transitions": []}
    result = add_nominal_thickness(kernel, prepared, rows, "revision")
    assert result["cells"][0]["nominal_thickness_mm"] == 0.2
    assert result["cells"][1]["nominal_thickness_mm"] is None
    assert result["cells"][1]["known_thickness_subtotal_mm"] == 0.2
    assert result["cells"][1]["unknown_thickness_ply_object_ids"] == ["B"]
    assert prepare_planar_coverage(rows, "group", "uncured")["thickness_basis"] == "uncured"


def test_reference_and_plane_mismatch_blocks_overlay():
    rows = _rows()
    rows[-1]["fields"]["composite_reference_surface_object_id"]["raw_value"] = "different"
    with pytest.raises(ValueError, match="common native reference"):
        prepare_planar_coverage(rows, "group", "cured")
    rows = _rows()
    rows[-1]["contour_planar_region"]["plane"]["origin_mm"][2] = 1
    with pytest.raises(ValueError, match="same verified plane"):
        prepare_planar_coverage(rows, "group", "cured")


def test_distinct_same_geometry_plies_remain_distinct_physical_layers():
    rows = _rows(second_region=_region(0, 0, 100, 100))
    prepared = prepare_planar_coverage(rows, "group", "cured")
    result = add_nominal_thickness({"status": "computed", "cells": [
        {"ply_object_ids": ["A", "B"], "area_mm2": 10000}]}, prepared, rows, "revision")
    assert result["cells"][0]["layer_count"] == 2
    assert math.isclose(result["cells"][0]["nominal_thickness_mm"], 0.5)


def test_unknown_native_layer_order_allows_unordered_thickness_without_claiming_stack_order():
    rows = _rows(second_region=_region(0, 0, 100, 100))
    rows[0]["order_status"] = "unavailable"
    rows[0]["ordered_child_object_ids"] = []
    rows[1]["order_status"] = "unavailable"
    rows[1]["ordered_child_object_ids"] = []
    rows[2]["order_status"] = "unavailable"
    rows[2]["ordered_child_object_ids"] = []
    rows[1]["parent_object_ids"] = ["group"]
    rows[2]["parent_object_ids"] = ["group"]
    rows[3]["parent_object_ids"] = ["s1"]
    rows[4]["parent_object_ids"] = ["s2"]
    prepared = prepare_planar_coverage(rows, "group", "cured")
    assert prepared["layer_order_status"] == "unavailable"
    assert prepared["ordered_ply_object_ids"] is None
    result = add_nominal_thickness({"status": "computed", "cells": [
        {"ply_object_ids": ["A", "B"], "area_mm2": 10000}]}, prepared, rows, "revision")
    assert result["cells"][0]["nominal_thickness_mm"] == pytest.approx(0.5)
    assert result["ordered_ply_object_ids"] is None


def test_group_rosette_change_invalidates_coverage_fingerprint():
    rows = _rows(second_region=_region(0, 0, 100, 100))
    rows[0]["fields"] = {"composite_rosette_x_x": {"raw_value": 1, "read_status": "available"}}
    prepared = prepare_planar_coverage(rows, "group", "cured")
    kernel = {"status": "computed", "cells": [{"ply_object_ids": ["A", "B"], "area_mm2": 10000}]}
    first = add_nominal_thickness(kernel, prepared, rows, "revision")["source_fingerprint"]
    rows[0]["fields"]["composite_rosette_x_x"]["raw_value"] = -1
    second = add_nominal_thickness(kernel, prepared, rows, "revision")["source_fingerprint"]
    assert first != second


@pytest.mark.skipif(os.getenv("CAA_TEST_FREECAD") != "1", reason="opt-in real FreeCAD integration")
def test_real_freecad_partitions_partial_patch_and_drop_off(tmp_path: Path):
    rows = _rows()
    settings = Settings()
    result = asyncio.run(compute_planar_coverage(rows, "group", "cured", "revision", "snapshot", settings, tmp_path))
    by_layers = {tuple(cell["ply_object_ids"]): cell for cell in result["cells"]}
    assert len(by_layers) == 2
    assert by_layers[("A",)]["area_mm2"] == pytest.approx(5000)
    assert by_layers[("A",)]["nominal_thickness_mm"] == pytest.approx(0.2)
    assert by_layers[("A", "B")]["area_mm2"] == pytest.approx(5000)
    assert by_layers[("A", "B")]["nominal_thickness_mm"] == pytest.approx(0.5)
    assert len(result["transitions"]) == 1
    assert result["transitions"][0]["length_mm"] == pytest.approx(100)
    assert result["transitions"][0]["kind"] == "internal_ply_termination"
    assert coverage_at_point(result, (25, 50, 0))["ply_object_ids"] == ["A", "B"]
    assert coverage_at_point(result, (75, 50, 0))["ply_object_ids"] == ["A"]
    assert coverage_at_point(result, (50, 50, 0))["status"] == "boundary_ambiguous"
    assert coverage_at_point(result, (150, 50, 0))["status"] == "outside_computed_regions"


@pytest.mark.skipif(os.getenv("CAA_TEST_FREECAD") != "1", reason="opt-in real FreeCAD integration")
def test_real_freecad_preserves_hole_disjoint_and_tangent_area(tmp_path: Path):
    def loop(role, points):
        return {"role": role, "sampled_points_mm": [[x, y, 0] for x, y in points]}
    square = lambda x0, y0, x1, y1: [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    job = {"plies": [
        {"object_id": "A", "loops": [loop("outer", square(0,0,100,100)),
                                      loop("inner", square(40,40,60,60))]},
        {"object_id": "B", "loops": [loop("outer", square(40,40,60,60))]},
        {"object_id": "C", "loops": [loop("outer", square(100,0,120,100))]},
    ]}
    settings = Settings()
    kernel = asyncio.run(run_freecad_job(Path(settings.cad_script_dir) / "composite_overlay.py",
                                         job, tmp_path, settings))
    assert kernel["status"] == "computed"
    areas = {tuple(cell["ply_object_ids"]): cell["area_mm2"] for cell in kernel["cells"]}
    assert areas == pytest.approx({("A",): 9600, ("B",): 400, ("C",): 2000})
    assert all(len(ids) == 1 for ids in areas)
    assert all(item["kind"] == "adjacent_distinct_coverage" for item in kernel["transitions"])
