from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.cad.result_validator import validate_parser_result


def minimal_result():
    revision_id = uuid4()
    root_id = uuid4()
    return {
        "revision_id": str(revision_id),
        "parser_name": "FreeCAD",
        "parser_version": "1.1.0",
        "schema_version": "1",
        "unit": "mm",
        "summary": {"face_count": 0, "edge_count": 0, "vertex_count": 0, "solid_count": 0},
        "entities": [
            {
                "id": str(root_id),
                "revision_id": str(revision_id),
                "parent_entity_id": None,
                "entity_type": "root",
                "tree_path": "/root",
                "sort_order": 0,
                "geometry": {},
                "metadata": {"assembly_hierarchy_preserved": False},
            }
        ],
        "relations": [],
        "meshes": [],
        "parse_manifest": {"source": "freecad"},
    }


def test_accepts_minimal_valid_parser_result():
    result = validate_parser_result(minimal_result())

    assert result.parser_name == "FreeCAD"
    assert result.entities[0].entity_type == "root"
    assert result.summary["face_count"] == 0


def test_rejects_result_missing_entities():
    data = minimal_result()
    del data["entities"]

    with pytest.raises(ValidationError):
        validate_parser_result(data)


def test_rejects_mesh_with_triangle_count_mismatch():
    data = minimal_result()
    entity_id = uuid4()
    data["meshes"] = [
        {
            "id": str(uuid4()),
            "revision_id": data["revision_id"],
            "entity_id": str(entity_id),
            "mesh_type": "face",
            "positions": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "indices": [[0, 1, 2]],
            "normals": None,
            "linear_deflection": 0.1,
            "vertex_count": 3,
            "triangle_count": 2,
        }
    ]

    with pytest.raises(ValidationError):
        validate_parser_result(data)
