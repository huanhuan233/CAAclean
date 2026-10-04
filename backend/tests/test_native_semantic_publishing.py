import json
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from app.component_builds.ingest import _publish_native_progress
from app.cad.repository import CadRepository


@pytest.mark.asyncio
async def test_native_publish_persists_typed_definition_without_replacing_feature_center(tmp_path):
    revision_id = uuid4()
    bundle = tmp_path / "native-caa"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1", "capture_status": "partial"}), encoding="utf-8")
    (bundle / "object_entities.jsonl").write_text(json.dumps({"object_id": "object_1", "document_id": "doc_1", "update_status": "up_to_date"}) + "\n", encoding="utf-8")
    (bundle / "tree_occurrences.jsonl").write_text(json.dumps({"occurrence_id": "occurrence_1", "object_id": "object_1", "document_id": "doc_1"}) + "\n", encoding="utf-8")
    (bundle / "native_features.jsonl").write_text(json.dumps({"native_feature_id": "semantic_facet_1", "feature_id": "object_1", "decoder_id": "NativeHoleDecoder", "native_hole": {"diameter_mm": 10}}) + "\n", encoding="utf-8")
    (bundle / "topology_entities.jsonl").write_text(json.dumps({"topology_id": "topology_1", "topology_kind": "face"}) + "\n", encoding="utf-8")
    (bundle / "property_facts.jsonl").write_text("", encoding="utf-8")
    recorded = {}

    class Repository:
        @asynccontextmanager
        async def native_publish_transaction(self):
            yield

        async def replace_native_tree_entities(self, _revision, rows, _expected):
            return len(rows)

        async def replace_native_property_facts(self, _revision, rows):
            return len(list(rows))

        async def replace_native_evidence(self, _revision, records_by_kind, *, replace_all=True):
            recorded["replace_all"] = replace_all
            recorded["records"] = {kind: list(records) for kind, records in records_by_kind.items()}
            return {kind: len(rows) for kind, rows in recorded["records"].items()}

        async def update_revision_manifest(self, _revision, payload):
            recorded["manifest"] = payload

    await _publish_native_progress(Repository(), revision_id, bundle)

    assert recorded["replace_all"] is False
    assert recorded["records"]["native_features"][0]["feature_id"] == "object_1"
    assert recorded["records"]["native_features"][0]["native_hole"]["diameter_mm"] == 10
    assert recorded["manifest"]["native_evidence_storage"]["counts"]["native_features"] == 1


@pytest.mark.asyncio
async def test_native_publish_preserves_mbd_definition_and_membership_without_projection_double_count(tmp_path):
    bundle = tmp_path / "native-caa"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    (bundle / "pmi_entities.jsonl").write_text(json.dumps({"pmi_id": "P1", "pmi_kind": "fta_set"}) + "\n", encoding="utf-8")
    (bundle / "pmi_associations.jsonl").write_text(json.dumps({"pmi_id": "P1", "target_id": "P1_TPS000001", "association_kind": "contains_annotation"}) + "\n", encoding="utf-8")
    (bundle / "fta_semantics.jsonl").write_text(json.dumps({"fta_semantic_id": "P1_TPS000001", "fta_set_id": "P1", "component_kind": "roughness"}) + "\n", encoding="utf-8")
    (bundle / "fta_sets.jsonl").write_text(json.dumps({"fta_set_id": "P1"}) + "\n", encoding="utf-8")
    recorded = {}

    class Repository:
        @asynccontextmanager
        async def native_publish_transaction(self):
            yield

        async def replace_native_evidence(self, _revision, streams, *, replace_all):
            recorded["records"] = {kind: list(rows) for kind, rows in streams.items()}
            return {kind: len(rows) for kind, rows in recorded["records"].items()}

        async def update_revision_manifest(self, _revision, payload):
            recorded["manifest"] = payload

    await _publish_native_progress(Repository(), uuid4(), bundle)
    assert set(recorded["records"]) == {"pmi_entities", "pmi_associations", "fta_sets", "fta_semantics"}
    assert recorded["manifest"]["native_evidence_storage"]["counts"]["fta_semantics"] == 1
    assert recorded["manifest"]["native_evidence_storage"]["counts"]["fta_sets"] == 1


def test_mbd_semantic_payload_normalizes_search_and_geometry_fields(tmp_path):
    from app.component_builds.caa_new_bundle import CaaNewBundleReader

    bundle = tmp_path / "native-caa"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    (bundle / "fta_semantics.jsonl").write_text(json.dumps({
        "fta_semantic_id": "A1", "fta_set_id": "P1", "component_kind": "dimension",
        "semantic_payload": {"native_alias": "孔径", "annotation_ttrs_count": 2,
                             "native_geometry_link_status": "native_ttrs_unmapped"},
    }) + "\n", encoding="utf-8")
    row = list(CaaNewBundleReader(bundle).native_evidence_streams()["fta_semantics"])[0]
    assert row["native_alias"] == "孔径"
    assert row["annotation_ttrs_count"] == 2
    assert row["native_geometry_link_status"] == "native_ttrs_unmapped"
    assert row["semantic_payload"]["native_alias"] == "孔径"


def test_mbd_bundle_rejects_broken_identity_and_declared_hash(tmp_path):
    from hashlib import sha256
    from app.component_builds.caa_new_bundle import CaaNewBundleError, CaaNewBundleReader

    bundle = tmp_path / "native-caa"
    bundle.mkdir()
    nodes = bundle / "pmi_entities.jsonl"
    nodes.write_text('{"pmi_id":"P1"}\n', encoding="utf-8")
    semantics = bundle / "fta_semantics.jsonl"
    semantics.write_text('{"fta_semantic_id":"A1","fta_set_id":"P1"}\n', encoding="utf-8")
    relations = bundle / "pmi_associations.jsonl"
    relations.write_text('{"pmi_id":"P1","target_id":"missing"}\n', encoding="utf-8")
    manifest = {"schema_version": "caa_capture_v1", "output_files": {
        "pmi_entities.jsonl": {"sha256": sha256(nodes.read_bytes()).hexdigest()}}}
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CaaNewBundleError, match="unresolved endpoint"):
        CaaNewBundleReader(bundle).native_evidence_streams()
    relations.write_text('{"pmi_id":"P1","target_id":"A1"}\n', encoding="utf-8")
    nodes.write_text('{"pmi_id":"P2"}\n', encoding="utf-8")
    with pytest.raises(CaaNewBundleError, match="hash mismatch"):
        CaaNewBundleReader(bundle).native_evidence_streams()


@pytest.mark.asyncio
async def test_missing_tree_channel_imports_evidence_without_replacing_tree(tmp_path):
    bundle = tmp_path / "native-caa"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    (bundle / "native_features.jsonl").write_text("", encoding="utf-8")

    recorded = {}

    class Repository:
        @asynccontextmanager
        async def native_publish_transaction(self):
            yield

        async def replace_native_tree_entities(self, *_args):
            raise AssertionError("existing tree must not be replaced")

        async def replace_native_property_facts(self, *_args):
            raise AssertionError("existing properties must not be replaced")

        async def replace_native_evidence(self, _revision, streams, *, replace_all):
            recorded["kinds"] = list(streams)
            assert replace_all is False
            return {kind: len(list(rows)) for kind, rows in streams.items()}

        async def update_revision_manifest(self, _revision, payload):
            recorded["manifest"] = payload

    await _publish_native_progress(Repository(), uuid4(), bundle)
    assert "native_features" in recorded["kinds"]
    assert "native_tree_storage" not in recorded["manifest"]
    assert "native_property_storage" not in recorded["manifest"]


@pytest.mark.asyncio
async def test_snapshot_stage_defers_commit_and_rolls_back_after_failure():
    calls = []

    class Session:
        async def flush(self):
            calls.append("flush")

        async def commit(self):
            calls.append("commit")

        async def rollback(self):
            calls.append("rollback")

    repository = CadRepository(Session())
    with pytest.raises(ValueError, match="bad evidence"):
        async with repository.native_publish_transaction():
            await repository._commit_native_stage()
            raise ValueError("bad evidence")
    assert calls == ["flush", "rollback"]


@pytest.mark.asyncio
async def test_partial_evidence_manifest_preserves_other_channel_counts():
    class Revision:
        parse_manifest = {
            "native_evidence_storage": {"counts": {"topology_entities": 4, "native_features": 2}},
        }

    class Repository(CadRepository):
        async def get_revision(self, _revision_id):
            return revision

        async def _commit_native_stage(self):
            pass

    revision = Revision()
    await Repository(None).update_revision_manifest(uuid4(), {
        "native_evidence_storage": {"counts": {"native_features": 3}},
    })
    assert revision.parse_manifest["native_evidence_storage"]["counts"] == {
        "topology_entities": 4, "native_features": 3,
    }
