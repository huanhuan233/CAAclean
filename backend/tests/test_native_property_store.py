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


def test_tube_geometry_and_formula_roundtrip_preserves_provenance():
    """验证新增工程属性完整通过数据库行与属性面板投影，不回读 JSONL。"""
    facts = [
        {"subject_id": "object_27", "key": "tube_bending_geometry",
         "value_type": "json", "raw_value": '{"segments":[{"rotation_deg":null}]}',
         "authority": "derived_geometry", "source_api": "AnalyzeTubePath",
         "read_status": "available", "tab_id": "tube_process", "group_id": "geometry"},
        {"subject_id": "object_27", "key": "formula_expression", "raw_value": "D / 2",
         "authority": "captured_native_tree", "source_api": "CATICkeRelationExp.Body(0)",
         "read_status": "available", "tab_id": "knowledgeware", "group_id": "formulas"},
    ]
    rows = native_property_rows(uuid4(), facts)
    for row, fact in zip(rows, facts):
        for key in ("raw_value", "source_api", "authority", "read_status"):
            assert row["payload"][key] == fact[key]
    result = build_database_properties(
        "object_27", {"node_id": "object_27", "object_id": "object_27"},
        [SimpleNamespace(subject_id=r["subject_id"], sort_order=r["sort_order"], payload=r["payload"]) for r in rows],
    )
    assert result["property_count"] == 2
    fields = [field for tab in result["tabs"] for group in tab["groups"] for field in group["fields"]]
    assert {f["raw_value"] for f in fields} == {f["raw_value"] for f in facts}
