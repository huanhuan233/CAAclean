from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


DOCUMENT_FORMAT = "component_spec_document_v1"


class ComponentSpecDocumentError(ValueError):
    """Raised when a ComponentSpec YAML document cannot be safely persisted."""


@dataclass(frozen=True)
class ComponentSpecDocument:
    data: dict[str, Any]
    yaml: str | None
    source_filename: str | None
    is_envelope: bool


def unpack_component_spec_document(stored: dict[str, Any]) -> ComponentSpecDocument:
    if stored.get("__format__") != DOCUMENT_FORMAT:
        return ComponentSpecDocument(
            data=stored,
            yaml=None,
            source_filename=None,
            is_envelope=False,
        )
    data = stored.get("data")
    if not isinstance(data, dict):
        raise ComponentSpecDocumentError("Stored ComponentSpec document data must be a mapping")
    yaml_text = stored.get("yaml")
    source_filename = stored.get("source_filename")
    return ComponentSpecDocument(
        data=data,
        yaml=yaml_text if isinstance(yaml_text, str) else None,
        source_filename=source_filename if isinstance(source_filename, str) else None,
        is_envelope=True,
    )


def pack_component_spec_document(
    data: dict[str, Any],
    yaml_text: str,
    source_filename: str | None = None,
) -> dict[str, Any]:
    return {
        "__format__": DOCUMENT_FORMAT,
        "data": data,
        "yaml": yaml_text,
        "source_filename": source_filename,
    }


def validate_component_spec_yaml(yaml_text: str, expected_data: dict[str, Any]) -> dict[str, Any]:
    parser = YAML(typ="safe")
    try:
        parsed = parser.load(yaml_text)
    except YAMLError as exc:
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ComponentSpecDocumentError(f"Invalid YAML{location}: {problem}") from exc

    if not isinstance(parsed, dict):
        raise ComponentSpecDocumentError("ComponentSpec YAML root must be a mapping")
    if parsed != expected_data:
        raise ComponentSpecDocumentError("ComponentSpec YAML does not match submitted data")
    return parsed
