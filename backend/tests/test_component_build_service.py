import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.component_builds.component_spec import component_spec_template
from app.component_builds.component_spec_document import pack_component_spec_document, unpack_component_spec_document
from app.component_builds.caa_new_bundle import CaaNewBundleReader
from app.component_builds.native_tree_store import NATIVE_SOURCE_PREFIX, native_tree_rows
from app.component_builds.repository import MemoryComponentBuildRepository, SqlAlchemyComponentBuildRepository
from app.component_builds.fusion import FusionSourceUnavailable, FusionSources
from app.component_builds.service import ComponentBuildService, SqlAlchemySourceStatusReader
from app.db.models import CadModelRevision, CadSpecTask, ComponentBuild


@pytest.mark.asyncio
async def test_step_bom_does_not_present_flattened_faces_and_datums_as_parts():
    revision_id = uuid4()
    root_id = uuid4()
    imported_face_id = uuid4()

    class Repository:
        async def list_structure_entities(self, requested_revision_id):
            assert requested_revision_id == revision_id
            return [
                SimpleNamespace(id=root_id, parent_entity_id=None, entity_type="root",
                                label="duoyimian234.stp", name="duoyimian234", source_ref="",
                                placement=None, volume=None, bounding_box=None, metadata_json={}),
                SimpleNamespace(id=imported_face_id, parent_entity_id=root_id,
                                entity_type="imported_object", label="FACE055", name="FACE055",
                                source_ref="FACE055", placement=None, volume=0,
                                bounding_box=None, metadata_json={}),
                SimpleNamespace(id=uuid4(), parent_entity_id=root_id, entity_type="imported_object",
                                label="XY-plane001", name="XY-plane001", source_ref="XY-plane001",
                                placement=None, volume=0, bounding_box=None, metadata_json={}),
            ]

    bom = await ComponentBuildService(Repository(), source_status_reader=FakeSourceStatusReader())._viewer_bom(
        SimpleNamespace(id=revision_id, source_file_name="duoyimian234.stp"),
        "STEP", {"assembly_hierarchy_preserved": False},
    )

    assert bom["assembly_mode"] == "unavailable"
    assert bom["hierarchy_status"] == "not_preserved"
    assert bom["part_count"] == 0
    assert [node["name"] for node in bom["nodes"]] == ["duoyimian234.stp"]
    assert bom["nodes"][0]["children"] == []


@pytest.mark.asyncio
async def test_step_bom_keeps_explicit_assembly_entities():
    revision_id = uuid4()
    assembly_id = uuid4()

    class Repository:
        async def list_structure_entities(self, _revision_id):
            return [
                SimpleNamespace(id=assembly_id, parent_entity_id=None, entity_type="assembly",
                                label="总成", name="总成", source_ref="", placement=None,
                                volume=None, bounding_box=None, metadata_json={}),
                SimpleNamespace(id=uuid4(), parent_entity_id=assembly_id, entity_type="part",
                                label="零件 A", name="零件 A", source_ref="A", placement=None,
                                volume=None, bounding_box=None, metadata_json={}),
            ]

    bom = await ComponentBuildService(Repository(), source_status_reader=FakeSourceStatusReader())._viewer_bom(
        SimpleNamespace(id=revision_id, source_file_name="assembly.stp"), "STEP", {}
    )

    assert bom["assembly_mode"] == "assembly"
    assert bom["part_count"] == 1
    assert bom["nodes"][0]["children"][0]["name"] == "零件 A"


@pytest.mark.asyncio
async def test_native_evidence_requires_complete_postgresql_storage_and_pages_in_order():
    revision_id = uuid4()
    build_id = uuid4()
    manifest = {"native_evidence_storage": {
        "backend": "postgresql", "complete": True, "counts": {"topology_cells": 2}
    }}

    class Repository:
        async def get_raw_revision(self, requested_id):
            assert requested_id == revision_id
            return SimpleNamespace(id=revision_id, parse_manifest=manifest)

        async def list_native_evidence(self, requested_id, kind, offset, limit):
            assert requested_id == revision_id and kind == "topology_cells"
            return [{"cell_id": "face-1"}, {"cell_id": "face-2"}][offset:offset + limit]

    service = ComponentBuildService(Repository(), source_status_reader=FakeSourceStatusReader())
    service._require_build = lambda _build_id: _async_value(SimpleNamespace(cad_revision_id=revision_id))
    first = await service.get_native_evidence(build_id, "topology_cells", 0, 1)
    assert first["records"] == [{"cell_id": "face-1"}]
    assert first["has_more"] is True and first["next_offset"] == 1
    second = await service.get_native_evidence(build_id, "topology_cells", 1, 1)
    assert second["records"] == [{"cell_id": "face-2"}]
    manifest["native_evidence_storage"]["complete"] = False
    with pytest.raises(ValueError, match="not persisted in PostgreSQL"):
        await service.get_native_evidence(build_id, "topology_cells", 0, 1)


@pytest.mark.asyncio
async def test_missing_optional_evidence_channel_is_not_reported_as_empty():
    revision_id = uuid4()

    class Repository:
        async def get_raw_revision(self, _revision_id):
            return SimpleNamespace(id=revision_id, parse_manifest={
                "native_evidence_storage": {"backend": "postgresql", "complete": True,
                                            "counts": {"features": 0}}
            })

    service = ComponentBuildService(Repository(), source_status_reader=FakeSourceStatusReader())
    service._require_build = lambda _build_id: _async_value(SimpleNamespace(cad_revision_id=revision_id))
    with pytest.raises(ValueError, match="not captured"):
        await service.get_native_evidence(uuid4(), "topology_cells", 0, 10)


@pytest.mark.asyncio
async def test_mbd_annotation_detail_uses_revision_scoped_database_and_preserves_unmapped_status():
    revision_id = uuid4()
    manifest = {"native_evidence_storage": {"backend": "postgresql", "complete": True,
                "counts": {"fta_semantics": 1, "pmi_entities": 1}}}

    class Repository:
        async def get_raw_revision(self, _revision_id):
            return SimpleNamespace(id=revision_id, parse_manifest=manifest)

        async def list_native_evidence(self, _revision_id, kind, offset, limit):
            return [{"fta_semantic_id": "A1"}] if kind == "fta_semantics" else [{"pmi_id": "P1"}]

        async def get_mbd_annotation(self, _revision_id, annotation_id):
            assert annotation_id == "A1"
            return [{"fta_semantic_id": "A1", "native_geometry_link_status": "native_ttrs_unmapped"}]

        async def list_mbd_relations(self, _revision_id, endpoint_id):
            return [{"pmi_id": "P1", "target_id": endpoint_id, "association_kind": "contains_annotation"}]

        async def list_mbd_annotations(self, _revision_id, **_filters):
            return [{"fta_semantic_id": "A1"}], 1

    service = ComponentBuildService(Repository(), source_status_reader=FakeSourceStatusReader())
    service._require_build = lambda _build_id: _async_value(SimpleNamespace(cad_revision_id=revision_id))
    detail = await service.get_mbd_annotation_detail(uuid4(), "A1")
    assert detail["native_geometry_status"] == "native_ttrs_unmapped"
    assert detail["render_mapping_status"] == "unmapped"
    listing = await service.list_mbd_annotations(uuid4(), offset=0, limit=10)
    assert listing["total"] == 1 and listing["has_more"] is False


@pytest.mark.asyncio
async def test_recognized_detail_reads_persisted_feature_and_measurements_on_demand():
    revision_id = uuid4()
    manifest = {"feature_evidence_storage": {"backend": "postgresql", "complete": True,
                "counts": {"canonical_features": 1, "measurements": 1}}}

    class Repository:
        async def get_raw_revision(self, _revision_id):
            return SimpleNamespace(id=revision_id, parse_manifest=manifest)

        async def list_native_evidence(self, _revision_id, kind, offset, limit):
            return [{"feature_center_id": "FC-1"}] if kind == "canonical_features" else [{"feature_center_id": "FC-1"}]

        async def get_feature_evidence_by_id(self, _revision_id, kind, feature_id):
            assert feature_id == "FC-1"
            return ([{"feature_center_id": "FC-1", "family": "hole"}] if kind == "canonical_features"
                    else [{"feature_center_id": "FC-1", "name": "diameter", "value": 10}])

    service = ComponentBuildService(Repository(), source_status_reader=FakeSourceStatusReader())
    service._require_build = lambda _build_id: _async_value(SimpleNamespace(cad_revision_id=revision_id))
    detail = await service.get_recognized_feature_detail(uuid4(), "FC-1")
    assert detail["feature"]["family"] == "hole"
    assert detail["measurements"][0]["value"] == 10
    manifest["feature_evidence_storage"]["complete"] = False
    with pytest.raises(ValueError, match="not persisted"):
        await service.get_recognized_feature_detail(uuid4(), "FC-1")


def test_native_brep_completeness_contract_preserves_database_values_and_old_bundles():
    """逐体完整性只透传数据库清单，旧包缺字段时不伪造零值。"""
    new_manifest = {"native_capture": {"available": True, "status": "complete",
                                       "exact_brep_body_count": 1, "incomplete_brep_body_count": 3}}
    new = ComponentBuildService._native_capture_contract("", new_manifest)
    assert new["exact_brep_body_count"] == 1
    assert new["incomplete_brep_body_count"] == 3
    old = ComponentBuildService._native_capture_contract("", {"native_capture": {"available": True}})
    assert old["exact_brep_body_count"] is None
    assert old["incomplete_brep_body_count"] is None


def find_build_node(nodes: list[dict], build_id: str) -> dict:
    for node in nodes:
        if node.get("node_type") == "build" and node.get("build_id") == build_id:
            return node
        found = find_build_node(node.get("children", []), build_id)
        if found:
            return found
    return {}


class FakeSourceStatusReader:
    async def get_step_status(self, revision_id):
        return {"status": "processing", "progress": 40}

    async def get_drawing_status(self, task_id):
        return {"status": "review_ready"}


class ReadyModelFailedDrawingReader:
    async def get_step_status(self, _revision_id):
        return {
            "status": "completed",
            "status_message": "ready",
            "progress": 100,
            "processing_route": "step_cad_parse",
            "source_format": "STEP",
        }

    async def get_drawing_status(self, _task_id):
        return {"status": "failed", "error_code": "DRAWING_FAILED", "error_message": "图纸解析失败"}


@pytest.mark.asyncio
async def test_ready_model_does_not_hide_failed_drawing_status():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="frame-001",
        component_name="带图纸框架",
        component_type="frame",
        cad_revision_id=uuid4(),
        drawing_task_id=uuid4(),
    )
    service = ComponentBuildService(repository, source_status_reader=ReadyModelFailedDrawingReader())

    response = await service.get_status(build.id)

    assert response["status"] == "source_failed"
    assert response["error_code"] == "DRAWING_FAILED"
    assert response["sources"]["drawing"]["error_code"] == "DRAWING_FAILED"


class FakeFusionSourceReader:
    def __init__(self, sources: FusionSources):
        self.sources = sources
        self.build_ids = []

    async def read(self, build):
        self.build_ids.append(build.id)
        return self.sources


@pytest.mark.asyncio
async def test_get_component_spec_normalizes_legacy_data_and_matching_yaml():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="legacy-001",
        component_name="Legacy",
        component_type="shaft",
    )
    await repository.save_component_spec(build.id, {"identity": {"name": "Legacy"}})
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    response = await service.get_component_spec(build.id)

    assert response["data"]["identity"]["name"] == "Legacy"
    assert response["data"]["schema_version"] == "1.2"
    from app.component_builds.component_spec_document import validate_component_spec_yaml
    assert validate_component_spec_yaml(response["yaml"], response["data"]) == response["data"]


def test_component_build_has_source_links():
    columns = ComponentBuild.__table__.columns

    assert columns["cad_model_id"].nullable is True
    assert columns["cad_revision_id"].nullable is True
    assert columns["drawing_task_id"].nullable is True
    assert columns["component_id"].nullable is False


@pytest.mark.asyncio
async def test_fuse_component_spec_saves_normalized_draft_and_returns_report():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="flange-001",
        component_name="XMS06-DN80",
        component_type="flange",
        family="connection-fastening",
        standard_number="HG/T 20592-2009",
        version="1.0.0",
    )
    reader = FakeFusionSourceReader(
        FusionSources(
            drawing_facts=[
                {
                    "fact_key": "product.component_type_raw",
                    "fact_type": "product_info",
                    "normalized_value": "带颈对焊",
                    "confidence": 0.9,
                    "metadata": {},
                }
            ],
            measurements=[],
            features=[],
        )
    )
    service = ComponentBuildService(
        repository,
        source_status_reader=FakeSourceStatusReader(),
        fusion_source_reader=reader,
    )

    response = await service.fuse_component_spec(build.id)

    assert reader.build_ids == [build.id]
    assert response["status"] == "completed"
    assert response["component_spec"]["identity"]["id"] == "flange-001"
    stored = unpack_component_spec_document((await repository.get_component_spec(build.id)).data)
    assert stored.data["identity"]["id"] == "flange-001"
    assert stored.yaml is not None


@pytest.mark.asyncio
async def test_fuse_component_spec_preserves_existing_manual_value():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="flange-001",
        component_name="XMS06-DN80",
        component_type="flange",
    )
    existing = component_spec_template.blank_data()
    existing["identity"]["name"] = "人工名称"
    await repository.save_component_spec(build.id, existing)
    service = ComponentBuildService(
        repository,
        source_status_reader=FakeSourceStatusReader(),
        fusion_source_reader=FakeFusionSourceReader(
            FusionSources(
                drawing_facts=[
                    {
                        "fact_key": "product.component_type_raw",
                        "fact_type": "product_info",
                        "normalized_value": "带颈对焊",
                        "confidence": 0.9,
                        "metadata": {},
                    }
                ],
                measurements=[],
                features=[],
            )
        ),
    )

    response = await service.fuse_component_spec(build.id)

    assert response["component_spec"]["identity"]["name"] == "人工名称"


@pytest.mark.asyncio
async def test_fuse_component_spec_reads_envelope_and_preserves_unknown_values():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="flange-001",
        component_name="XMS06-DN80",
        component_type="flange",
    )
    existing = component_spec_template.blank_data()
    existing["identity"]["name"] = "Manual name"
    yaml_text = (
        f"{component_spec_template.render_yaml(existing)}\n"
        "# custom extension\ncustom_extension:\n  curve_policy: all\n"
    )
    existing["custom_extension"] = {"curve_policy": "all"}
    await repository.save_component_spec(
        build.id,
        pack_component_spec_document(existing, yaml_text, "manual.yaml"),
    )
    service = ComponentBuildService(
        repository,
        source_status_reader=FakeSourceStatusReader(),
        fusion_source_reader=FakeFusionSourceReader(
            FusionSources(
                drawing_facts=[
                    {
                        "fact_key": "product.component_type_raw",
                        "fact_type": "product_info",
                        "normalized_value": "weld neck",
                        "confidence": 0.9,
                        "metadata": {},
                    }
                ],
                measurements=[],
                features=[],
            )
        ),
    )

    response = await service.fuse_component_spec(build.id)
    stored = unpack_component_spec_document((await repository.get_component_spec(build.id)).data)

    assert response["component_spec"]["identity"]["name"] == "Manual name"


@pytest.mark.asyncio
async def test_viewer_contract_uses_controlled_urls_and_optional_feature_center():
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="aero-general-001",
        component_name="航空框架",
        component_type="aero-general-part",
        standard_number="RIB-03",
        version="03.1",
        cad_revision_id=revision_id,
    )
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        status="completed",
        status_message="ready",
        source_file_ext=".catpart",
        error_code=None,
        error_message=None,
        parse_manifest={
            "ingest": {"source_format": "CATPART", "processing_route": "catia_feature_center"},
            "viewer_asset": {
                "glb": "feature-center/lightweight/model.glb",
                "scene_manifest": "feature-center/manifest.json",
                "face_mesh_map": "feature-center/lightweight/face_mesh_map.json",
                "feature_mesh_map": "feature-center/lightweight/feature_mesh_map.json",
                "selection_index": "feature-center/lightweight/selection_index.json",
            },
            "feature_center": {
                "available": True,
                "mapping_available": True,
                "feature_face_mapping_count": 3,
                "canonical_features": "feature-center/canonical_features.jsonl",
                "feature_geometry_links": "feature-center/feature_geometry_links.jsonl",
            },
            "native_semantics": {
                "available": True,
                "features": "native-caa/features.jsonl",
                "feature_topology_links": "native-caa/native_feature_topology_links.jsonl",
                "capabilities": "native-caa/capabilities.json",
            },
        },
    ))
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    contract = await service.get_viewer_contract(build.id)

    assert contract["status"] == "ready"
    assert contract["source_format"] == "CATPART"
    assert contract["summary"]["part_number"] == "RIB-03"
    assert contract["summary"]["part_name"] == "航空框架"
    assert contract["summary"]["version"] == "03.1"
    assert contract["viewer_asset"]["glb_url"].startswith(f"/api/component-builds/{build.id}/viewer/assets/")
    assert "cad-work" not in contract["viewer_asset"]["glb_url"]
    assert contract["viewer_asset"]["selection_index_url"].endswith("feature-center/lightweight/selection_index.json")
    assert contract["feature_center"]["available"] is True
    assert contract["feature_center"]["mapping_available"] is True
    assert contract["native_semantics"]["feature_topology_links_url"].endswith(
        "native-caa/native_feature_topology_links.jsonl"
    )
    assert contract["native_semantics"]["capabilities_url"].endswith("native-caa/capabilities.json")
    assert contract["summary"]["feature_face_mapping_available"] is True


@pytest.mark.asyncio
async def test_viewer_contract_builds_catproduct_bom_from_native_product_instances(tmp_path):
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="assy-001",
        component_name="CATProduct Assy",
        component_type="assembly",
        cad_revision_id=revision_id,
    )
    native_dir = tmp_path / str(revision_id) / "native-caa"
    native_dir.mkdir(parents=True)
    records = [
        {
            "instance_id": "PRDINS_000001",
            "parent_instance_id": "",
            "instance_name": "RootProduct",
            "reference_id": "PRDREF_ROOT",
            "instance_path": "RootProduct",
            "depth": 0,
            "child_index": 0,
            "child_count": 2,
            "transform_4x4": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        },
        {
            "instance_id": "PRDINS_000002",
            "parent_instance_id": "PRDINS_000001",
            "instance_name": "Bracket.1",
            "reference_id": "PRDREF_BRACKET",
            "instance_path": "RootProduct/Bracket.1",
            "depth": 1,
            "child_index": 1,
            "child_count": 0,
        },
        {
            "instance_id": "PRDINS_000003",
            "parent_instance_id": "PRDINS_000001",
            "instance_name": "Bolt.1",
            "reference_id": "PRDREF_BOLT",
            "instance_path": "RootProduct/Bolt.1",
            "depth": 1,
            "child_index": 2,
            "child_count": 0,
        },
    ]
    with (native_dir / "product_instances.jsonl").open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        status="completed",
        status_message="ready",
        progress=100,
        source_file_ext=".catproduct",
        source_file_name="RootProduct.CATProduct",
        source_file_path=str(tmp_path / str(revision_id) / "source.CATProduct"),
        error_code=None,
        error_message=None,
        parse_manifest={
            "ingest": {"source_format": "CATPRODUCT", "processing_route": "catia_feature_center"},
            "viewer_asset": {
                "glb": "feature-center/lightweight/model.glb",
                "scene_manifest": "feature-center/manifest.json",
                "face_mesh_map": "feature-center/lightweight/face_mesh_map.json",
                "feature_mesh_map": "feature-center/lightweight/feature_mesh_map.json",
            },
            "native_semantics": {
                "available": True,
                "product_instances": "native-caa/product_instances.jsonl",
            },
        },
    ))
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    contract = await service.get_viewer_contract(build.id)

    assert contract["bom"]["assembly_mode"] == "assembly"
    assert contract["bom"]["part_count"] == 2
    root = contract["bom"]["nodes"][0]
    assert root["name"] == "RootProduct"
    assert [child["name"] for child in root["children"]] == ["Bracket.1", "Bolt.1"]
    assert root["children"][0]["assembly_path"] == "RootProduct/Bracket.1"


@pytest.mark.asyncio
async def test_viewer_contract_builds_catproduct_bom_from_caa_new_product_occurrences(tmp_path):
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="assy-new-001",
        component_name="CAA New Assy",
        component_type="assembly",
        cad_revision_id=revision_id,
    )
    native_dir = tmp_path / str(revision_id) / "native-caa"
    native_dir.mkdir(parents=True)
    _write_jsonl(
        native_dir / "product_occurrences.jsonl",
        [
            {
                "occurrence_id": "product_occurrence_1",
                "parent_occurrence_id": "",
                "instance_name": "RootProduct",
                "part_number": "ROOT-PN",
                "reference_id": "product_reference_1",
                "occurrence_path": "/0:RootProduct",
                "depth": 0,
                "source_index": 0,
                "child_count": 2,
            },
            {
                "occurrence_id": "product_occurrence_3",
                "parent_occurrence_id": "product_occurrence_1",
                "instance_name": "Bolt.1",
                "part_number": "BOLT-PN",
                "reference_id": "product_reference_2",
                "occurrence_path": "/0:RootProduct/2:Bolt.1",
                "depth": 1,
                "source_index": 2,
                "child_count": 0,
            },
            {
                "occurrence_id": "product_occurrence_2",
                "parent_occurrence_id": "product_occurrence_1",
                "instance_name": "Bracket.1",
                "part_number": "BRACKET-PN",
                "reference_id": "product_reference_2",
                "occurrence_path": "/0:RootProduct/1:Bracket.1",
                "depth": 1,
                "source_index": 1,
                "child_count": 0,
            },
        ],
    )
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        status="completed",
        status_message="ready",
        progress=100,
        source_file_ext=".catproduct",
        source_file_name="RootProduct.CATProduct",
        source_file_path=str(tmp_path / str(revision_id) / "source.CATProduct"),
        error_code=None,
        error_message=None,
        parse_manifest={
            "ingest": {"source_format": "CATPRODUCT", "processing_route": "catia_feature_center"},
            "viewer_asset": {},
            "native_capture": {"available": True, "has_tree": True, "has_properties": False},
            "native_semantics": {
                "available": True,
                "product_occurrences": "native-caa/product_occurrences.jsonl",
                "tree_occurrences": "native-caa/tree_occurrences.jsonl",
            },
        },
    ))
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    contract = await service.get_viewer_contract(build.id)

    assert contract["bom"]["assembly_mode"] == "assembly"
    root = contract["bom"]["nodes"][0]
    assert root["part_number"] == "ROOT-PN"
    assert [child["name"] for child in root["children"]] == ["Bracket.1", "Bolt.1"]
    assert root["children"][0]["part_number"] == "BRACKET-PN"
    assert "product_reference_2" not in root["children"][0]["part_number"]


@pytest.mark.asyncio
async def test_viewer_contract_reports_empty_catproduct_geometry():
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="assy-empty-001",
        component_name="Empty Geometry Assy",
        component_type="assembly",
        cad_revision_id=revision_id,
    )
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        status="completed",
        status_message="ready",
        progress=100,
        source_file_ext=".catproduct",
        source_file_name="RootProduct.CATProduct",
        error_code=None,
        error_message=None,
        parse_manifest={
            "ingest": {"source_format": "CATPRODUCT", "processing_route": "catia_feature_center"},
            "viewer_asset": {
                "glb": "feature-center/lightweight/model.glb",
                "scene_manifest": "feature-center/manifest.json",
                "face_mesh_map": "feature-center/lightweight/face_mesh_map.json",
                "feature_mesh_map": "feature-center/lightweight/feature_mesh_map.json",
            },
            "viewer_summary": {"solid_count": 0},
            "feature_center_manifest": {
                "lightweight": {"primitive_count": 0, "triangle_count": 0},
            },
        },
    ))
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    contract = await service.get_viewer_contract(build.id)

    assert contract["viewer_geometry"]["displayable"] is False
    assert contract["viewer_geometry"]["triangle_count"] == 0
    assert contract["viewer_geometry"]["empty_reason"] == "catproduct_missing_loaded_representations"


@pytest.mark.asyncio
async def test_viewer_contract_keeps_native_capture_ready_without_viewer_asset():
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="catpart-native-only",
        component_name="Native Only",
        component_type="part",
        cad_revision_id=revision_id,
    )
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        status="completed",
        status_message="ready",
        progress=100,
        source_file_ext=".catpart",
        source_file_name="NativeOnly.CATPart",
        error_code=None,
        error_message=None,
        parse_manifest={
            "ingest": {"source_format": "CATPART", "processing_route": "catia_feature_center"},
            "viewer_asset": {},
            "native_capture": {
                "available": True,
                "status": "partial",
                "schema_version": "caa_capture_v1",
                "parser_version": "0.2.0",
                "capture_engine": "caa_new",
                "capture_platform": "intel_a",
                "capture_bitness": 32,
                "has_tree": True,
                "has_properties": True,
                "has_topology": False,
                "has_geometry": False,
                "has_mesh": False,
            },
            "native_semantics": {
                "available": True,
                "tree_occurrences": "native-caa/tree_occurrences.jsonl",
                "property_facts": "native-caa/property_facts.jsonl",
            },
            "feature_center_manifest": {"lightweight": {"primitive_count": 0, "triangle_count": 0}},
        },
    ))

    contract = await ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader()).get_viewer_contract(build.id)

    assert contract["status"] == "ready"
    assert contract["viewer_asset"] is None
    assert contract["native_capture"]["available"] is True
    assert contract["native_capture"]["capture_engine"] == "caa_new"
    assert contract["native_capture"]["capture_platform"] == "intel_a"
    assert contract["native_capture"]["capture_bitness"] == 32
    assert contract["native_capture"]["tree_url"].endswith("native-caa/tree_occurrences.jsonl")


@pytest.mark.asyncio
async def test_viewer_contract_exposes_progressive_native_tree_while_geometry_is_processing():
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="catproduct-progressive",
        component_name="Progressive Assembly",
        component_type="assembly",
        cad_revision_id=revision_id,
    )
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        status="processing",
        status_message="feature_center_processing",
        progress=70,
        source_file_ext=".catproduct",
        source_file_name="Progressive.CATProduct",
        error_code=None,
        error_message=None,
        parse_manifest={
            "ingest": {"source_format": "CATPRODUCT", "processing_route": "catia_feature_center"},
            "native_capture": {"available": True, "has_tree": True},
            "native_semantics": {
                "available": True,
                "manifest": "native-caa/manifest.json",
                "tree_occurrences": "native-caa/tree_occurrences.jsonl",
            },
        },
    ))

    contract = await ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader()).get_viewer_contract(build.id)

    assert contract["status"] == "processing"
    assert contract["current_stage"] == "feature_center_processing"
    assert contract["viewer_asset"] is None
    assert contract["native_capture"]["has_tree"] is True
    assert contract["native_capture"]["tree_url"].endswith("native-caa/tree_occurrences.jsonl")
    assert contract["native_semantics"]["tree_occurrences_url"].endswith("native-caa/tree_occurrences.jsonl")


@pytest.mark.asyncio
async def test_native_tree_api_reads_postgresql_level_without_file_fallback(tmp_path):
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="native-tree-db",
        component_name="Database Tree",
        component_type="assembly",
        cad_revision_id=revision_id,
    )
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        parse_manifest={"native_tree_storage": {"backend": "postgresql", "node_count": 2, "complete": True}},
    ))
    root_entity = SimpleNamespace(
        id=uuid4(),
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
            "node_kind": "product_occurrence",
            "display_name": "500.000",
            "has_children": True,
        },
    )
    child_entity = SimpleNamespace(
        id=uuid4(), parent_entity_id=root_entity.id, source_ref="caa-native:child",
        source_index=1, sort_order=1, name="510.000.2", label="510.000.2",
        tree_path="/500.000/510.000.2",
        metadata_json={"native_tree": True, "native_node_id": "child", "parent_id": "root",
                       "node_kind": "product_occurrence", "display_name": "510.000.2"},
    )
    repository.list_native_tree_entities = lambda _revision_id, parent_node_id=None, **_options: _async_value(
        [root_entity] if parent_node_id is None else ([child_entity] if parent_node_id == "root" else [])
    )
    repository.count_native_tree_entities = lambda _revision_id: _async_value(2)

    tree = await ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader()).get_native_tree(
        build.id,
        SimpleNamespace(cad_work_dir=tmp_path),
    )

    assert tree["schema_version"] == "caa_native_tree_db_v1"
    assert tree["node_count"] == 2
    assert tree["total_node_count"] == 2
    assert tree["roots"][0]["node_id"] == "root"
    assert tree["roots"][0]["children"][0]["display_name"] == "510.000.2"


@pytest.mark.asyncio
async def test_native_tree_api_includes_parameter_value_from_postgresql_facts(tmp_path):
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="native-tree-parameter",
        component_name="Database Tree Parameter",
        component_type="part",
        cad_revision_id=revision_id,
    )
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        parse_manifest={"native_tree_storage": {"backend": "postgresql", "node_count": 2, "complete": True}},
    ))
    root_entity = SimpleNamespace(
        id=uuid4(), parent_entity_id=None, source_ref="caa-native:root",
        source_index=0, sort_order=0, name="Part10", label="Part10", tree_path="/Part10",
        metadata_json={"native_tree": True, "native_node_id": "root", "display_name": "Part10"},
    )
    parameter_entity = SimpleNamespace(
        id=uuid4(), parent_entity_id=root_entity.id, source_ref="caa-native:parameter",
        source_index=1, sort_order=1, name="材料编号", label="材料编号", tree_path="/Part10/材料编号",
        metadata_json={
            "native_tree": True,
            "native_node_id": "parameter",
            "parent_id": "root",
            "display_name": "材料编号",
            "object_id": "object_parameter",
            "startup_type": "String",
        },
    )
    repository.list_native_tree_entities = lambda _revision_id, parent_node_id=None, **_options: _async_value(
        [root_entity] if parent_node_id is None else ([parameter_entity] if parent_node_id == "root" else [])
    )
    repository.count_native_tree_entities = lambda _revision_id: _async_value(2)
    repository.list_native_property_facts = lambda _revision_id, subject_ids, **_options: _async_value([
        SimpleNamespace(
            subject_id="object_parameter",
            sort_order=0,
            payload={
                "key": "catia_parameter_value_text",
                "raw_value": "M00001453",
                "display_value": "M00001453",
                "raw_display_text": "M00001453",
            },
        )
    ] if "object_parameter" in subject_ids else [])

    tree = await ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader()).get_native_tree(
        build.id,
        SimpleNamespace(cad_work_dir=tmp_path),
    )

    assert tree["roots"][0]["children"][0]["parameter_value"] == "M00001453"


@pytest.mark.asyncio
async def test_native_tree_defaults_to_visible_catia_occurrences_but_can_query_supplemental():
    revision_id = uuid4()
    build_id = uuid4()
    root = SimpleNamespace(metadata_json={"node_id": "root", "presentation_status": "visible"},
                           source_ref="caa-native:root", source_index=0, sort_order=0,
                           name="Part1", label="Part1", tree_path="/Part1")
    primary = SimpleNamespace(metadata_json={"node_id": "plies", "parent_id": "root",
                                "presentation_status": "visible"},
                              source_ref="caa-native:plies", source_index=1, sort_order=1,
                              name="Plies Group", label="Plies Group", tree_path="/Part1/Plies Group")
    supplemental = SimpleNamespace(metadata_json={"node_id": "sag", "parent_id": "root",
                                     "presentation_status": "non_primary"},
                                   source_ref="caa-native:sag", source_index=2, sort_order=2,
                                   name="Sag", label="Sag", tree_path="/Part1/Sag")

    class Repository:
        async def get_raw_revision(self, _revision_id):
            return SimpleNamespace(id=revision_id, parse_manifest={
                "native_tree_storage": {"backend": "postgresql", "node_count": 3, "complete": True}
            })

        async def count_native_tree_entities(self, _revision_id):
            return 3

        async def list_native_tree_entities(self, _revision_id, parent_node_id=None, *,
                                            offset=0, limit=None, include_supplemental=True):
            rows = [root] if parent_node_id is None else [primary, supplemental]
            if not include_supplemental:
                rows = [row for row in rows if row.metadata_json["presentation_status"] == "visible"]
            return rows[offset:offset + limit] if limit is not None else rows[offset:]

        async def list_native_property_facts(self, *_args, **_kwargs):
            return []

    service = ComponentBuildService(Repository(), source_status_reader=FakeSourceStatusReader())
    service._require_build = lambda _build_id: _async_value(SimpleNamespace(cad_revision_id=revision_id))
    visible = await service.get_native_tree(build_id, SimpleNamespace(), parent_id="root", page_size=1)
    assert [node["node_id"] for node in visible["roots"]] == ["plies"]
    assert visible["has_more"] is False
    all_nodes = await service.get_native_tree(build_id, SimpleNamespace(), include_supplemental=True,
                                              parent_id="root", page_size=1)
    assert [node["node_id"] for node in all_nodes["roots"]] == ["plies"]
    assert all_nodes["has_more"] is True


@pytest.mark.asyncio
async def test_native_tree_api_reads_caa_new_bundle_without_local_paths(tmp_path):
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="native-tree",
        component_name="Native Tree",
        component_type="assembly",
        cad_revision_id=revision_id,
    )
    native_dir = tmp_path / str(revision_id) / "native-caa"
    native_dir.mkdir(parents=True)
    _write_json(native_dir / "manifest.json", {"schema_version": "caa_capture_v1", "parser_version": "0.2.0", "capture_status": "partial"})
    _write_jsonl(
        native_dir / "product_occurrences.jsonl",
        [
            {
                "occurrence_id": "product_occurrence_1",
                "parent_occurrence_id": "",
                "reference_id": "product_reference_root",
                "referenced_document_id": "doc_1",
                "instance_name": "Root",
                "part_number": "Root",
                "source_index": 0,
                "depth": 0,
                "child_count": 2,
            },
            {
                "occurrence_id": "product_occurrence_3",
                "parent_occurrence_id": "product_occurrence_1",
                "reference_id": "product_reference_part",
                "referenced_document_id": "doc_2",
                "instance_name": "Part.2",
                "part_number": "Part",
                "source_index": 2,
                "depth": 1,
                "child_count": 0,
            },
            {
                "occurrence_id": "product_occurrence_2",
                "parent_occurrence_id": "product_occurrence_1",
                "reference_id": "product_reference_part",
                "referenced_document_id": "doc_2",
                "instance_name": "Part.1",
                "part_number": "Part",
                "source_index": 1,
                "depth": 1,
                "child_count": 0,
            },
        ],
    )
    _write_jsonl(
        native_dir / "object_entities.jsonl",
        [
            {
                "object_id": "object_1",
                "document_id": "doc_2",
                "object_kind": "catia_spec_object",
                "display_name": "D:\\secret\\Part.CATPart",
                "internal_name": "Part1",
                "startup_type": "MechanicalPart",
                "update_status": "up_to_date",
            }
        ],
    )
    _write_jsonl(
        native_dir / "tree_occurrences.jsonl",
        [
            {
                "occurrence_id": "occurrence_1",
                "parent_occurrence_id": "product_occurrence_2",
                "object_id": "object_1",
                "document_id": "doc_2",
                "product_occurrence_id": "product_occurrence_2",
                "reference_id": "product_reference_part",
                "source_index": 1,
                "occurrence_kind": "native_feature",
                "presentation_status": "visible",
            }
        ],
    )
    _write_jsonl(
        native_dir / "property_facts.jsonl",
        [
            {
                "property_id": "property_fact_1",
                "subject_id": "product_occurrence_2",
                "tab_id": "product",
                "tab_label": "产品",
                "group_id": "identity",
                "group_label": "标识",
                "key": "path",
                "display_name": "路径",
                "raw_value": "D:\\secret\\Part.CATPart",
                "display_value": "D:\\secret\\Part.CATPart",
                "display_order": 10,
                "read_only": True,
            }
        ],
    )
    payload = CaaNewBundleReader(native_dir).build_tree()
    rows = native_tree_rows(revision_id, payload)
    entities = [SimpleNamespace(
        id=row["id"], parent_entity_id=row["parent_entity_id"], source_ref=row["source_ref"],
        source_index=row["source_index"], sort_order=row["sort_order"], name=row["name"],
        label=row["label"], tree_path=row["tree_path"], metadata_json=row["metadata_json"],
    ) for row in rows]
    entity_ids = {entity.source_ref.removeprefix(NATIVE_SOURCE_PREFIX): entity.id for entity in entities}
    repository.get_raw_revision = lambda _revision_id: _async_value(SimpleNamespace(
        id=revision_id,
        parse_manifest={
            "native_tree_storage": {"backend": "postgresql", "node_count": len(entities), "complete": True},
            "native_property_storage": {"backend": "postgresql", "fact_count": 1, "complete": True},
            "native_semantics": {
                "available": True,
                "manifest": "native-caa/manifest.json",
            }
        },
    ))
    repository.count_native_tree_entities = lambda _revision_id: _async_value(len(entities))
    repository.list_native_tree_entities = lambda _revision_id, parent_node_id=None, **_options: _async_value([
        entity for entity in entities
        if entity.parent_entity_id == (entity_ids[parent_node_id] if parent_node_id else None)
    ])
    repository.get_native_tree_entity = lambda _revision_id, node_id: _async_value(next(
        (entity for entity in entities if entity.source_ref == NATIVE_SOURCE_PREFIX + node_id), None
    ))
    repository.list_native_property_facts = lambda _revision_id, subject_ids, **_options: _async_value([
        SimpleNamespace(
            subject_id="product_occurrence_2",
            sort_order=0,
            payload={
                "property_id": "property_fact_1",
                "subject_id": "product_occurrence_2",
                "tab_id": "product",
                "tab_label": "产品",
                "group_id": "identity",
                "group_label": "标识",
                "key": "path",
                "display_name": "路径",
                "raw_value": "D:\\secret\\Part.CATPart",
                "display_value": "D:\\secret\\Part.CATPart",
                "display_order": 10,
                "read_only": True,
            },
        )
    ])
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    tree = await service.get_native_tree(build.id, SimpleNamespace(cad_work_dir=tmp_path))
    part_children = await service.get_native_tree(
        build.id, SimpleNamespace(cad_work_dir=tmp_path), parent_id="product_occurrence_2"
    )
    properties = await service.get_native_node_properties(build.id, "product_occurrence_2", SimpleNamespace(cad_work_dir=tmp_path))

    root = tree["roots"][0]
    assert [child["display_name"] for child in root["children"]] == ["Part.1", "Part.2"]
    assert part_children["roots"][0]["display_name"] == "Part.CATPart"
    assert "D:\\secret" not in json.dumps(tree)
    assert properties["property_count"] == 1
    assert properties["tabs"][0]["groups"][0]["fields"][0]["display_value"] == "<local_path>\\Part.CATPart"


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_selected_native_node_properties_include_definition_semantics_and_instance_context():
    revision_id = uuid4()
    build_id = uuid4()
    node_id = "occurrence_2"
    metadata = {"object_id": "object_7", "occurrence_id": node_id, "document_id": "doc_1",
                "product_occurrence_id": "product_occurrence_2"}

    class Repository:
        async def get_raw_revision(self, _revision_id):
            return SimpleNamespace(id=revision_id, parse_manifest={
                "native_property_storage": {"backend": "postgresql", "complete": True},
                "native_evidence_storage": {"backend": "postgresql", "complete": True,
                                            "counts": {"native_features": 1}},
            })

        async def get_native_tree_entity(self, _revision_id, _node_id):
            return SimpleNamespace(metadata_json=metadata)

        async def list_native_property_facts(self, _revision_id, _subjects):
            return []

        async def get_native_feature(self, _revision_id, object_id):
            assert object_id == "object_7"
            return {"feature_id": "object_7", "decoder_id": "NativePadDecoder", "decode_level": "typed",
                    "native_prism": {"is_thin": False, "second_limit": {"dimension_mm": 0}}}

    service = ComponentBuildService(Repository(), source_status_reader=FakeSourceStatusReader())
    service._require_build = lambda _build_id: _async_value(SimpleNamespace(cad_revision_id=revision_id))

    detail = await service.get_native_node_properties(build_id, node_id, None)

    assert detail["revision_id"] == str(revision_id)
    assert detail["object_id"] == "object_7"
    assert detail["product_occurrence_id"] == "product_occurrence_2"
    assert detail["native_feature"]["native_prism"]["is_thin"] is False
    assert detail["native_feature"]["native_prism"]["second_limit"]["dimension_mm"] == 0


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")


@pytest.mark.asyncio
async def test_fuse_component_spec_preserves_uploaded_schema_version():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="future-001",
        component_name="Future",
        component_type="shaft",
    )
    existing = component_spec_template.blank_data()
    existing["schema_version"] = "1.3"
    await repository.save_component_spec(
        build.id,
        pack_component_spec_document(existing, "schema_version: '1.3'\n", "future.yaml"),
    )
    service = ComponentBuildService(
        repository,
        source_status_reader=FakeSourceStatusReader(),
        fusion_source_reader=FakeFusionSourceReader(
            FusionSources(
                drawing_facts=[{
                    "fact_key": "product.component_type_raw",
                    "fact_type": "product_info",
                    "normalized_value": "shaft",
                    "confidence": 0.9,
                    "metadata": {},
                }],
                measurements=[],
                features=[],
            )
        ),
    )

    response = await service.fuse_component_spec(build.id)

    assert response["component_spec"]["schema_version"] == "1.3"


@pytest.mark.asyncio
async def test_fuse_component_spec_rejects_build_without_available_sources():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="flange-001",
        component_name="XMS06-DN80",
        component_type="flange",
    )
    service = ComponentBuildService(
        repository,
        source_status_reader=FakeSourceStatusReader(),
        fusion_source_reader=FakeFusionSourceReader(FusionSources([], [], [])),
    )

    with pytest.raises(FusionSourceUnavailable, match="no_sources_available"):
        await service.fuse_component_spec(build.id)


@pytest.mark.asyncio
async def test_status_projects_linked_source_states():
    model_id = uuid4()
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository(revision_models={revision_id: model_id})
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    status = await service.get_status(build.id)

    assert status["status"] == "parsing_sources"
    assert status["sources"]["reference_step"]["status"] == "processing"
    assert status["sources"]["drawing"]["status"] == "missing"


@pytest.mark.asyncio
async def test_status_prioritizes_failed_sources_and_manual_layout_review():
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={task_id: revision_id},
    )
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=task_id)

    class FailedStepStatusReader:
        async def get_step_status(self, revision_id):
            return {"status": "failed"}

        async def get_drawing_status(self, task_id):
            return {"status": "needs_manual_layout"}

    status = await ComponentBuildService(repository, source_status_reader=FailedStepStatusReader()).get_status(build.id)

    assert status["status"] == "source_failed"


@pytest.mark.asyncio
async def test_tree_detail_and_status_share_the_same_projected_build_status():
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={task_id: revision_id},
    )
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        status="parsing_sources",
    )
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=task_id)

    class ReadySourceStatusReader:
        async def get_step_status(self, _revision_id):
            return {"status": "completed", "progress": 100}

        async def get_drawing_status(self, _task_id):
            return {"status": "review_ready", "progress": 100}

    service = ComponentBuildService(repository, source_status_reader=ReadySourceStatusReader())

    tree = await service.get_tree()
    detail = await service.get_build(build.id)
    source_status = await service.get_status(build.id)

    assert find_build_node(tree, str(build.id))["status"] == "sources_ready"
    assert detail["status"] == "sources_ready"
    assert source_status["status"] == "sources_ready"


@pytest.mark.asyncio
async def test_unlinked_build_retains_persisted_upload_failure_status():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        status="source_failed",
    )
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    detail = await service.get_build(build.id)
    status = await service.get_status(build.id)

    assert detail["status"] == "source_failed"
    assert status["status"] == "source_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step_status", "drawing_status"),
    [("completed", "review_ready"), ("processing", "needs_manual_layout")],
)
async def test_persisted_source_failure_overrides_ready_and_manual_source_states(step_status, drawing_status):
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={task_id: revision_id},
    )
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        status="source_failed",
    )
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=task_id)
    class SourceStatusReader:
        async def get_step_status(self, _revision_id):
            return {"status": step_status, "progress": 100}

        async def get_drawing_status(self, _task_id):
            return {"status": drawing_status, "progress": 100}

    service = ComponentBuildService(repository, source_status_reader=SourceStatusReader())

    tree = await service.get_tree()
    detail = await service.get_build(build.id)
    status = await service.get_status(build.id)

    assert find_build_node(tree, str(build.id))["status"] == "source_failed"
    assert detail["status"] == "source_failed"
    assert status["status"] == "source_failed"


@pytest.mark.asyncio
async def test_source_status_reader_projects_source_errors_when_available():
    revision = SimpleNamespace(
        status="failed",
        progress=100,
        status_message="parser failed",
        error_code="freecad_failed",
        error_message="FreeCAD exited",
    )
    task = SimpleNamespace(status="failed", progress=100)

    class Session:
        async def get(self, model, _identifier):
            return revision if model is CadModelRevision else task

    reader = SqlAlchemySourceStatusReader(Session())

    step = await reader.get_step_status(uuid4())
    drawing = await reader.get_drawing_status(uuid4())

    assert step["status_message"] == "parser failed"
    assert step["error_code"] == "freecad_failed"
    assert step["error_message"] == "FreeCAD exited"
    assert drawing["status_message"] is None
    assert drawing["error_code"] is None
    assert drawing["error_message"] is None


@pytest.mark.asyncio
async def test_tree_keeps_fusion_disabled_until_a_source_is_attached():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")

    tree = await ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader()).get_tree()

    version_node = find_build_node(tree, str(build.id))
    assert version_node["build_id"] == str(build.id)
    assert [child["node_type"] for child in version_node["children"]] == [
        "folder", "data_fusion", "component_spec", "publish_validation"
    ]
    fusion, component_spec, publish = version_node["children"][1:]
    assert fusion["disabled"] is True and fusion["status"] == "pending"
    assert component_spec["disabled"] is False and component_spec["status"] == "draft"
    assert publish["disabled"] is True and publish["status"] == "future"
    assert fusion["status_label"] == "待上传来源"
    assert component_spec["status_label"] == "待填写"
    assert publish["status_label"] == "后续能力"


@pytest.mark.asyncio
async def test_tree_enables_fusion_when_build_has_a_source_and_marks_saved_draft_completed():
    model_id = uuid4()
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository(revision_models={revision_id: model_id})
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    ready_tree = await service.get_tree()
    ready_fusion = find_build_node(ready_tree, str(build.id))["children"][1]

    assert ready_fusion["id"] == f"{build.id}:fusion"
    assert ready_fusion["build_id"] == str(build.id)
    assert ready_fusion["disabled"] is False
    assert ready_fusion["status"] == "ready"
    assert ready_fusion["status_label"] == "可开始"

    await repository.save_component_spec(build.id, component_spec_template.blank_data())
    completed_tree = await service.get_tree()
    completed_fusion = find_build_node(completed_tree, str(build.id))["children"][1]

    assert completed_fusion["disabled"] is False
    assert completed_fusion["status"] == "completed"
    assert completed_fusion["status_label"] == "已生成草稿"


@pytest.mark.asyncio
async def test_get_build_projects_identity_links_and_timestamps():
    model_id = uuid4()
    revision_id = uuid4()
    drawing_task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={drawing_task_id: revision_id},
    )
    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        default_dn=80,
        default_pn=16,
        error_code="source_unavailable",
        error_message="STEP parser did not respond",
    )
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=drawing_task_id)
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    result = await service.get_build(build.id)

    assert result["component_id"] == "xms06"
    assert result["default_dn"] == 80
    assert result["cad_model_id"] == str(model_id)
    assert result["cad_revision_id"] == str(revision_id)
    assert result["drawing_task_id"] == str(drawing_task_id)
    assert result["error_code"] == "source_unavailable"
    assert result["error_message"] == "STEP parser did not respond"
    assert result["created_at"] is not None
    assert result["updated_at"] is not None


@pytest.mark.asyncio
async def test_memory_repository_accepts_explicit_component_version():
    repository = MemoryComponentBuildRepository()

    build = await repository.create_build(
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        version="2.1.0",
    )

    assert build.version == "2.1.0"


@pytest.mark.asyncio
async def test_memory_repository_defaults_component_version():
    repository = MemoryComponentBuildRepository()

    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")

    assert build.version == "1.0.0"


@pytest.mark.asyncio
async def test_unconfigured_memory_repository_accepts_trusted_source_ids():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=task_id)

    assert build.cad_model_id == model_id
    assert build.cad_revision_id == revision_id
    assert build.drawing_task_id == task_id


@pytest.mark.asyncio
async def test_memory_repository_clears_drawing_when_step_revision_is_replaced():
    model_id = uuid4()
    revision_a = uuid4()
    revision_b = uuid4()
    drawing_task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_a: model_id, revision_b: model_id},
        drawing_task_revisions={drawing_task_id: revision_a},
    )
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_a)
    await repository.attach_drawing(build.id, task_id=drawing_task_id)

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_b)

    assert build.cad_revision_id == revision_b
    assert build.drawing_task_id is None


@pytest.mark.asyncio
async def test_memory_repository_preserves_drawing_when_step_revision_is_reattached():
    model_id = uuid4()
    revision_id = uuid4()
    drawing_task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={drawing_task_id: revision_id},
    )
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    await repository.attach_drawing(build.id, task_id=drawing_task_id)

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)

    assert build.drawing_task_id == drawing_task_id


@pytest.mark.asyncio
async def test_memory_repository_lists_newest_builds_first_with_uuid_tie_breaker():
    repository = MemoryComponentBuildRepository()
    timestamp = datetime(2026, 7, 23, tzinfo=timezone.utc)
    oldest = await repository.create_build(
        id=UUID(int=1),
        component_id="old",
        component_name="Old",
        component_type="flange",
        created_at=timestamp - timedelta(seconds=1),
    )
    tied_lower = await repository.create_build(
        id=UUID(int=2),
        component_id="low",
        component_name="Low",
        component_type="flange",
        created_at=timestamp,
    )
    tied_higher = await repository.create_build(
        id=UUID(int=3),
        component_id="high",
        component_name="High",
        component_type="flange",
        created_at=timestamp,
    )

    builds = await repository.list_builds()

    assert [build.id for build in builds] == [tied_higher.id, tied_lower.id, oldest.id]


@pytest.mark.asyncio
async def test_memory_repository_rejects_step_revision_from_another_model():
    model_id = uuid4()
    revision_id = uuid4()
    repository = MemoryComponentBuildRepository(revision_models={revision_id: uuid4()})
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")

    with pytest.raises(ValueError, match="revision does not belong to model"):
        await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)


@pytest.mark.asyncio
async def test_memory_repository_rejects_drawing_task_from_another_revision():
    model_id = uuid4()
    revision_id = uuid4()
    task_id = uuid4()
    repository = MemoryComponentBuildRepository(
        revision_models={revision_id: model_id},
        drawing_task_revisions={task_id: uuid4()},
    )
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)

    with pytest.raises(ValueError, match="drawing task does not belong to build revision"):
        await repository.attach_drawing(build.id, task_id=task_id)


class SourceLookupSession:
    def __init__(self, build, revision, task):
        self.build = build
        self.revision = revision
        self.task = task

    async def get(self, model, _identifier):
        if model is ComponentBuild:
            return self.build
        if model is CadModelRevision:
            return self.revision
        if model is CadSpecTask:
            return self.task
        return None

    async def commit(self):
        return None

    async def refresh(self, _build):
        return None


@pytest.mark.asyncio
async def test_sqlalchemy_repository_rejects_step_revision_from_another_model():
    build = ComponentBuild(id=uuid4(), component_id="xms06", component_name="XMS06", component_type="flange")
    session = SourceLookupSession(build, SimpleNamespace(model_id=uuid4()), None)
    repository = SqlAlchemyComponentBuildRepository(session)

    with pytest.raises(ValueError, match="revision does not belong to model"):
        await repository.attach_step(build.id, model_id=uuid4(), revision_id=uuid4())


@pytest.mark.asyncio
async def test_sqlalchemy_repository_rejects_drawing_task_from_another_revision():
    revision_id = uuid4()
    build = ComponentBuild(id=uuid4(), component_id="xms06", component_name="XMS06", component_type="flange", cad_revision_id=revision_id)
    session = SourceLookupSession(build, None, SimpleNamespace(revision_id=uuid4()))
    repository = SqlAlchemyComponentBuildRepository(session)

    with pytest.raises(ValueError, match="drawing task does not belong to build revision"):
        await repository.attach_drawing(build.id, task_id=uuid4())


@pytest.mark.asyncio
async def test_sqlalchemy_repository_clears_drawing_when_step_revision_is_replaced():
    model_id = uuid4()
    revision_a = uuid4()
    revision_b = uuid4()
    drawing_task_id = uuid4()
    build = ComponentBuild(
        id=uuid4(),
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        cad_model_id=model_id,
        cad_revision_id=revision_a,
        drawing_task_id=drawing_task_id,
    )
    session = SourceLookupSession(build, SimpleNamespace(model_id=model_id), None)
    repository = SqlAlchemyComponentBuildRepository(session)

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_b)

    assert build.cad_revision_id == revision_b
    assert build.drawing_task_id is None


@pytest.mark.asyncio
async def test_sqlalchemy_repository_preserves_drawing_when_step_revision_is_reattached():
    model_id = uuid4()
    revision_id = uuid4()
    drawing_task_id = uuid4()
    build = ComponentBuild(
        id=uuid4(),
        component_id="xms06",
        component_name="XMS06",
        component_type="flange",
        cad_model_id=model_id,
        cad_revision_id=revision_id,
        drawing_task_id=drawing_task_id,
    )
    session = SourceLookupSession(build, SimpleNamespace(model_id=model_id), None)
    repository = SqlAlchemyComponentBuildRepository(session)

    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)

    assert build.drawing_task_id == drawing_task_id
