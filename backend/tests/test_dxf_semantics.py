from pathlib import Path

import ezdxf

from app.dxf.source import parse_source


def test_block_occurrences_are_distinct_and_text_is_source_semantics(tmp_path: Path):
    drawing = ezdxf.new("R2013")
    block = drawing.blocks.new("MARK")
    block.add_line((0, 0), (2, 0))
    model = drawing.modelspace()
    model.add_blockref("MARK", (0, 0))
    model.add_blockref("MARK", (10, 0))
    model.add_text("中文标记", dxfattribs={"height": 2})
    model.add_mtext("第一行\\P第二行")
    path = tmp_path / "semantics.dxf"
    drawing.saveas(path)

    document = parse_source(path, "rev")

    assert document["counts"]["source_entities"] == 4
    assert len(document["occurrences"]) == 2
    assert document["occurrences"][0]["object_id"] != document["occurrences"][1]["object_id"]
    assert document["occurrences"][0]["definition_handle"] == document["occurrences"][1]["definition_handle"]
    assert [item["display_text"] for item in document["entities"] if item["type"] in {"TEXT", "MTEXT"}] == [
        "中文标记", "第一行\n第二行"]


def test_dimension_and_hatch_do_not_become_independent_solids(tmp_path: Path):
    drawing = ezdxf.new("R2013")
    model = drawing.modelspace()
    model.add_linear_dim(base=(0, 3), p1=(0, 0), p2=(10, 0), text="12").render()
    hatch = model.add_hatch(color=2)
    hatch.paths.add_polyline_path([(0, 0), (10, 0), (10, 5), (0, 5)], is_closed=True)
    path = tmp_path / "annotation.dxf"
    drawing.saveas(path)

    document = parse_source(path, "rev")

    dimension = next(item for item in document["entities"] if item["type"] == "DIMENSION")
    fill = next(item for item in document["entities"] if item["type"] == "HATCH")
    assert dimension["raw_text"] == "12"
    assert dimension["measurement"] == 10
    assert fill["boundary_path_count"] == 1
    assert document["counts"]["source_entities"] == 2


def test_minsert_expansion_keeps_four_occurrence_ids(tmp_path: Path):
    drawing = ezdxf.new("R2013")
    block = drawing.blocks.new("CELL")
    block.add_line((0, 0), (1, 0))
    drawing.modelspace().add_blockref("CELL", (5, 7)).grid((2, 2), (10, 20))
    path = tmp_path / "array.dxf"
    drawing.saveas(path)

    document = parse_source(path, "rev")

    assert document["counts"]["source_entities"] == 1
    assert document["counts"]["occurrences"] == 4
    assert len({item["object_id"] for item in document["occurrences"]}) == 4
    assert len({item["definition_handle"] for item in document["occurrences"]}) == 1
