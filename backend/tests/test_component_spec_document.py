import pytest

from app.component_builds.component_spec_document import (
    DOCUMENT_FORMAT,
    ComponentSpecDocumentError,
    pack_component_spec_document,
    unpack_component_spec_document,
    validate_component_spec_yaml,
)


def test_unpack_treats_legacy_plain_mapping_as_component_data():
    stored = {"identity": {"name": "Legacy flange"}}

    document = unpack_component_spec_document(stored)

    assert document.data == stored
    assert document.yaml is None
    assert document.source_filename is None
    assert document.is_envelope is False


def test_pack_and_unpack_preserve_yaml_and_source_filename():
    data = {"identity": {"name": "Uploaded flange"}, "custom": {"rating": 3}}
    yaml_text = "# keep this comment\nidentity:\n  name: Uploaded flange\ncustom:\n  rating: 3\n"

    stored = pack_component_spec_document(data, yaml_text, "flange-v1.3.yaml")
    document = unpack_component_spec_document(stored)

    assert stored["__format__"] == DOCUMENT_FORMAT
    assert document.data == data
    assert document.yaml == yaml_text
    assert document.source_filename == "flange-v1.3.yaml"
    assert document.is_envelope is True


def test_validate_accepts_mapping_root_and_returns_plain_data():
    yaml_text = "# component\nidentity:\n  name: \"Flange\"\nenabled: true\ncount: 2\n"

    parsed = validate_component_spec_yaml(
        yaml_text,
        {"identity": {"name": "Flange"}, "enabled": True, "count": 2},
    )

    assert parsed == {"identity": {"name": "Flange"}, "enabled": True, "count": 2}


@pytest.mark.parametrize(
    ("yaml_text", "message"),
    [
        ("identity: [\n", "YAML"),
        ("- identity\n- name\n", "mapping"),
        ("plain scalar\n", "mapping"),
    ],
)
def test_validate_rejects_invalid_or_non_mapping_yaml(yaml_text, message):
    with pytest.raises(ComponentSpecDocumentError, match=message):
        validate_component_spec_yaml(yaml_text, {})


def test_validate_rejects_yaml_that_differs_from_submitted_data():
    with pytest.raises(ComponentSpecDocumentError, match="does not match"):
        validate_component_spec_yaml("identity:\n  name: YAML name\n", {"identity": {"name": "Form name"}})


def test_validate_accepts_equivalent_nested_mapping_and_scalar_values():
    data = {
        "identity": {"id": "flange-001", "aliases": ["A", "B"]},
        "nullable": None,
        "ratio": 1.5,
    }
    yaml_text = "identity:\n  id: flange-001\n  aliases: [A, B]\nnullable: null\nratio: 1.5\n"

    assert validate_component_spec_yaml(yaml_text, data) == data
