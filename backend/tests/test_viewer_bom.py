from app.component_builds.viewer_bom import build_bom_contract


def test_empty_structure_returns_no_bom():
    contract = build_bom_contract([], "STEP")

    assert contract == {"assembly_mode": "none", "default_visible": False, "part_count": 0, "nodes": []}


def test_single_part_defaults_to_collapsed_bom():
    roots = [
        {
            "id": "root",
            "parent_entity_id": None,
            "entity_type": "root",
            "label": "零件",
            "source_ref": "Part",
            "children": [
                {
                    "id": "part-1",
                    "parent_entity_id": "root",
                    "entity_type": "imported_object",
                    "label": "主体",
                    "source_ref": "Body",
                    "children": [],
                }
            ],
        }
    ]

    contract = build_bom_contract(roots, "CATPART")

    assert contract["assembly_mode"] == "single_part"
    assert contract["default_visible"] is False
    assert contract["part_count"] == 1
    assert contract["nodes"][0]["children"][0]["source_format"] == "CATPART"


def test_real_multi_part_tree_defaults_to_visible_bom_and_keeps_mapping():
    roots = [
        {
            "id": "assembly",
            "parent_entity_id": None,
            "entity_type": "assembly",
            "label": "总成",
            "source_ref": "Product1",
            "children": [
                {
                    "id": "part-a",
                    "parent_entity_id": "assembly",
                    "entity_type": "part",
                    "label": "零件 A",
                    "source_ref": "A.1",
                    "metadata": {
                        "part_number": "A",
                        "version": "03.1",
                        "material": "铝合金",
                        "quantity": 2,
                        "assembly_path": "ROOT/A.1",
                        "constraint_status": "positioned",
                        "constraint_count": 3,
                        "mesh_primitive_ids": ["P1", "P2"],
                    },
                    "placement": {"matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]},
                    "children": [],
                },
                {
                    "id": "part-b",
                    "parent_entity_id": "assembly",
                    "entity_type": "part",
                    "label": "零件 B",
                    "source_ref": "B.1",
                    "children": [],
                },
            ],
        }
    ]

    contract = build_bom_contract(roots, "STEP")

    assert contract["assembly_mode"] == "assembly"
    assert contract["default_visible"] is True
    assert contract["part_count"] == 2
    part = contract["nodes"][0]["children"][0]
    assert part["part_number"] == "A"
    assert part["quantity"] == 2
    assert part["version"] == "03.1"
    assert part["material"] == "铝合金"
    assert part["assembly_path"] == "ROOT/A.1"
    assert part["constraint_status"] == "positioned"
    assert part["constraint_count"] == 3
    assert part["mesh_primitive_ids"] == ["P1", "P2"]
    assert part["transform"] is not None
