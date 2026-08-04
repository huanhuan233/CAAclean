from pathlib import Path

import pytest

from app.component_builds.ingest import (
    IngestSourceError,
    identify_source,
    redact_local_paths,
    safe_asset_path,
)


@pytest.mark.parametrize(
    ("name", "source_format", "route"),
    [
        ("part.step", "STEP", "step_cad_parse"),
        ("PART.STP", "STEP", "step_cad_parse"),
        ("零件 (终版).CATPart", "CATPART", "catia_feature_center"),
        ("零件.catpart", "CATPART", "catia_feature_center"),
    ],
)
def test_source_format_is_derived_from_real_file_name(name, source_format, route):
    source = identify_source(name)

    assert source.source_format == source_format
    assert source.processing_route == route


@pytest.mark.parametrize("name", ["wrong.cart", "part.zip", "part", "part.CATProduct"])
def test_unsupported_source_is_rejected(name):
    with pytest.raises(IngestSourceError) as error:
        identify_source(name)

    assert error.value.code == "UNSUPPORTED_SOURCE_FORMAT"


def test_asset_path_cannot_escape_task_directory(tmp_path):
    root = tmp_path / "task"
    root.mkdir()
    valid = root / "feature-center" / "lightweight" / "model.glb"
    valid.parent.mkdir(parents=True)
    valid.write_bytes(b"glTF")

    assert safe_asset_path(root, "feature-center/lightweight/model.glb") == valid
    with pytest.raises(IngestSourceError):
        safe_asset_path(root, "../secret.txt")
    with pytest.raises(IngestSourceError):
        safe_asset_path(root, str(Path(tmp_path) / "outside.glb"))


def test_external_tool_error_does_not_expose_local_absolute_path():
    message = redact_local_paths(r"CATIA failed at D:\cad-work\task\source.CATPart")

    assert "D:\\" not in message
    assert "<local_path>" in message
