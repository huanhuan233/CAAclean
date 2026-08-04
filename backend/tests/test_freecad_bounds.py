import ast
from pathlib import Path

from freecad_scripts.bounds import is_usable_bbox, union_bbox


def test_infinite_kernel_axis_sentinel_is_not_a_model_bounding_box():
    axis_box = {"min": [-1e100, 0.0, 0.0], "max": [1e100, 0.0, 0.0]}
    solid_box = {"min": [-206.0, -230.0, -32.7], "max": [206.0, 280.0, 35.0]}

    assert is_usable_bbox(axis_box) is False
    assert union_bbox([axis_box, solid_box]) == solid_box


def test_bbox_union_keeps_finite_geometry_extent():
    boxes = [
        {"min": [-2.0, -1.0, 0.0], "max": [1.0, 3.0, 2.0]},
        {"min": [0.0, -4.0, -1.0], "max": [5.0, 2.0, 4.0]},
    ]

    assert union_bbox(boxes) == {"min": [-2.0, -4.0, -1.0], "max": [5.0, 3.0, 4.0]}


def test_freecad_entry_script_remains_syntax_valid_without_importing_freecad():
    source = Path("freecad_scripts/parse_step.py").read_text(encoding="utf-8")

    ast.parse(source)
