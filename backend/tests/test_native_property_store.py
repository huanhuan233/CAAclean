from types import SimpleNamespace
from uuid import uuid4

from app.component_builds.native_property_store import build_database_properties, native_property_rows


def test_native_property_rows_preserve_all_facts_and_build_tabs_without_files():
    revision_id = uuid4()
    facts = [
        {
            "property_id": "p2",
            "subject_id": "object_3",
            "tab_id": "product",
            "tab_label": "产品",
            "group_id": "identity",
            "group_label": "标识",
            "key": "path",
            "display_name": "路径",
            "raw_value": r"D:\secret\Part.CATPart",
            "display_value": r"D:\secret\Part.CATPart",
            "display_order": 20,
            "read_only": True,
        },
        {
            "property_id": "p1",
            "subject_id": "occurrence_3",
            "tab_id": "product",
            "tab_label": "产品",
            "group_id": "identity",
            "group_label": "标识",
            "key": "name",
            "display_name": "名称",
            "display_value": "Part65",
            "display_order": 10,
        },
    ]

    rows = native_property_rows(revision_id, facts)
    result = build_database_properties(
        "occurrence_3",
        {"node_id": "occurrence_3", "occurrence_id": "occurrence_3", "object_id": "object_3"},
        [SimpleNamespace(subject_id=row["subject_id"], sort_order=row["sort_order"], payload=row["payload"]) for row in rows],
    )

    assert len(rows) == 2
    assert result["property_count"] == 2
    fields = result["tabs"][0]["groups"][0]["fields"]
    assert [field["display_name"] for field in fields] == ["名称", "路径"]
    assert fields[1]["display_value"] == r"<local_path>\Part.CATPart"
