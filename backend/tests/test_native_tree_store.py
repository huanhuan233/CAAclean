from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.component_builds.native_tree_store import build_database_tree, native_tree_rows, order_native_tree_rows


def test_native_tree_rows_preserve_every_node_and_parent_link():
    revision_id = uuid4()
    payload = {
        "schema_version": "caa_capture_v1",
        "parser_version": "0.2.0",
        "capture_status": "complete",
        "node_count": 3,
        "roots": [
            {
                "node_id": "root",
                "parent_id": "",
                "node_kind": "product_occurrence",
                "display_name": "500.000",
                "internal_name": "500.000",
                "startup_type": "CATProduct",
                "source_index": 0,
                "tree_path": "/500.000",
                "has_children": True,
                "children": [
                    {
                        "node_id": "part",
                        "parent_id": "root",
                        "node_kind": "product_occurrence",
                        "display_name": "510.000.1",
                        "internal_name": "510.000",
                        "startup_type": "CATPart",
                        "source_index": 1,
                        "tree_path": "/500.000/510.000.1",
                        "has_children": True,
                        "children": [
                            {
                                "node_id": "feature",
                                "parent_id": "part",
                                "node_kind": "native_feature",
                                "display_name": "PartBody",
                                "internal_name": "PartBody",
                                "startup_type": "PartBody",
                                "source_index": 1,
                                "tree_path": "/500.000/510.000.1/PartBody",
                                "has_children": False,
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    rows = native_tree_rows(revision_id, payload)

    assert len(rows) == 3
    assert rows[0]["entity_type"] == "root"
    assert rows[1]["entity_type"] == "part"
    assert rows[2]["entity_type"] == "native_feature"
    assert rows[1]["parent_entity_id"] == rows[0]["id"]
    assert rows[2]["parent_entity_id"] == rows[1]["id"]
    assert rows[2]["metadata_json"]["native_node_id"] == "feature"
    assert rows[1]["metadata_json"]["child_count"] == 1


def test_database_tree_returns_only_requested_level_with_total_count():
    revision_id = uuid4()
    root_id = uuid4()
    child_id = uuid4()
    entities = [
        SimpleNamespace(
            id=root_id,
            parent_entity_id=None,
            source_ref="caa-native:root",
            source_index=0,
            sort_order=0,
            name="500.000",
            label="500.000",
            tree_path="/500.000",
            metadata_json={
                "native_tree": True,
                "native_node_id": "root",
                "display_name": "500.000",
                "node_kind": "product_occurrence",
                "has_children": True,
            },
        ),
        SimpleNamespace(
            id=child_id,
            parent_entity_id=root_id,
            source_ref="caa-native:child",
            source_index=1,
            sort_order=1,
            name="510.000",
            label="510.000.1",
            tree_path="/500.000/510.000.1",
            metadata_json={
                "native_tree": True,
                "native_node_id": "child",
                "parent_id": "root",
                "display_name": "510.000.1",
                "node_kind": "product_occurrence",
                "has_children": False,
            },
        ),
    ]

    root_page = build_database_tree(entities[:1], total_node_count=2)
    child_page = build_database_tree(entities[1:], total_node_count=2)

    assert root_page["node_count"] == 1
    assert root_page["total_node_count"] == 2
    assert root_page["roots"][0]["node_id"] == "root"
    assert root_page["roots"][0]["children"] == []
    assert child_page["roots"][0]["parent_id"] == "root"


def test_unordered_rows_are_parent_first_across_batch_boundary():
    revision_id = uuid4()
    ids = [uuid4() for _ in range(1005)]
    rows = [
        {"id": entity_id, "revision_id": revision_id,
         "parent_entity_id": ids[i - 1] if i else None,
         "source_ref": f"caa-native:{i}", "sort_order": i}
        for i, entity_id in enumerate(ids)
    ]
    ordered = order_native_tree_rows(list(reversed(rows)))
    assert ordered == rows


@pytest.mark.parametrize("invalid", ["missing", "cycle", "self_cycle", "duplicate"])
def test_invalid_parent_graph_is_rejected_without_discarding_links(invalid):
    root, child = uuid4(), uuid4()
    rows = [
        {"id": root, "parent_entity_id": None, "source_ref": "caa-native:root"},
        {"id": child, "parent_entity_id": root, "source_ref": "caa-native:child"},
    ]
    if invalid == "missing":
        rows[1]["parent_entity_id"] = uuid4()
    elif invalid == "cycle":
        rows[0]["parent_entity_id"] = child
    elif invalid == "self_cycle":
        rows[1]["parent_entity_id"] = child
    else:
        rows.append(dict(rows[1]))
    with pytest.raises(ValueError, match="missing parent|cycle|duplicate"):
        order_native_tree_rows(rows)


def test_repeated_nested_node_is_rejected():
    node = {"node_id": "root", "children": []}
    with pytest.raises(ValueError, match="duplicate node_id"):
        native_tree_rows(uuid4(), {"roots": [node, node]})
