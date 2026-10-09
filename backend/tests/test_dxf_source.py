from pathlib import Path

import ezdxf
import pytest

from app.component_builds.ingest import identify_source
from app.dxf.source import parse_source


def test_dxf_route_is_independent_of_step_and_catia():
    source = identify_source("drawing.DXF")
    assert (source.source_format, source.processing_route) == ("DXF", "dxf_cad_parse")
    assert identify_source("product.ZIP").source_format == "CATPRODUCT"


def test_source_entities_keep_handles_vertices_and_empty_layers(tmp_path: Path):
    drawing = ezdxf.new("R2000", setup=False)
    drawing.header["$INSUNITS"] = 4
    drawing.layers.new("EMPTY")
    drawing.layers.new("OUTLINE")
    first = drawing.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True,
                                                 dxfattribs={"layer": "OUTLINE"})
    second = drawing.modelspace().add_lwpolyline([(20, 0), (21, 0)], dxfattribs={"layer": "OUTLINE"})
    path = tmp_path / "drawing.dxf"
    drawing.saveas(path)

    result = parse_source(path, "revision-a")

    assert result["counts"]["source_entities"] == 2
    assert result["counts"]["vertices"] == 6
    assert {item["source_handle"] for item in result["entities"]} == {first.dxf.handle, second.dxf.handle}
    assert result["entities"][0]["object_id"] != result["entities"][1]["object_id"]
    assert result["entities"][0]["closed"] is True
    assert len(result["entities"][0]["vertices"]) == 4
    assert "EMPTY" in [layer["name"] for layer in result["layers"]]
    assert all(item["layer"] != "EMPTY" for item in result["entities"])


def test_renamed_dwg_is_rejected(tmp_path: Path):
    path = tmp_path / "renamed.dxf"
    path.write_bytes(b"AC1032 DWG data")
    with pytest.raises(ValueError, match="DXF_HEADER_INVALID"):
        parse_source(path, "revision-a")
