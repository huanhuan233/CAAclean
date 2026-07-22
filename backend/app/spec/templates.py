from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal


def sanitize_template_structure(template: dict[str, Any] | None, *, mode: Literal["structure_only", "field-template"] = "structure_only") -> dict[str, Any]:
    if not template:
        return {"parameters": []}
    if mode != "structure_only":
        return deepcopy(template)
    return {
        "schema_version": template.get("schema_version"),
        "template_mode": "skeleton",
        "parameters": [
            {"name": parameter["name"]}
            for parameter in template.get("parameters", [])
            if isinstance(parameter, dict) and parameter.get("name")
        ],
    }

