"""Opt-in PostgreSQL transaction and query smoke for imported MBD evidence."""

from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.cad.repository import CadRepository
from app.component_builds.native_persistence import publish_native_capture
from app.component_builds.repository import SqlAlchemyComponentBuildRepository
from app.component_builds.service import ComponentBuildService, SqlAlchemySourceStatusReader
from app.core.config import Settings
from app.db.models import CadModel, CadModelRevision, ComponentBuild


@pytest.mark.asyncio
async def test_p5_real_postgres_mbd_pagination_and_detail(tmp_path) -> None:
    if os.environ.get("P5_LIVE_DB") != "1":
        pytest.skip("set P5_LIVE_DB=1 to use the configured local PostgreSQL")
    bundle = tmp_path / "native-caa"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1", "capture_status": "partial"}), encoding="utf-8")
    (bundle / "pmi_entities.jsonl").write_text("".join(json.dumps(row) + "\n" for row in (
        {"pmi_id": "P1", "pmi_kind": "fta_set", "subject_id": "D1"},
        {"pmi_id": "V1", "pmi_kind": "fta_view", "subject_id": "D1"})), encoding="utf-8")
    annotations = [
        {"fta_semantic_id": "A1", "fta_set_id": "P1", "component_kind": "dimension", "read_status": "partial",
         "semantic_payload": {"native_alias": "孔径", "annotation_ttrs_count": 2,
                              "native_geometry_link_status": "native_ttrs_unmapped", "raw_fields": [
             {"key": "nominal_value", "raw_value": "10", "unit": "mm", "read_status": "available"}]}},
        {"fta_semantic_id": "A2", "fta_set_id": "P1", "component_kind": "roughness", "read_status": "partial",
         "native_geometry_link_status": "unresolved", "semantic_payload": {"raw_fields": []}},
    ]
    (bundle / "fta_semantics.jsonl").write_text("".join(json.dumps(row) + "\n" for row in annotations), encoding="utf-8")
    (bundle / "pmi_associations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in (
        {"pmi_id": "P1", "target_id": "A1", "association_kind": "contains_annotation", "read_status": "available"},
        {"pmi_id": "V1", "target_id": "A1", "association_kind": "view_contains_annotation", "read_status": "available"})), encoding="utf-8")
    model_id, revision_id, build_id = uuid4(), uuid4(), uuid4()
    engine = create_async_engine(Settings().database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            session.add(CadModel(id=model_id, name="P5 MBD transaction smoke"))
            await session.flush()
            session.add(CadModelRevision(
                id=revision_id, model_id=model_id, revision_no=1,
                source_file_name="p5-smoke.CATPart", source_file_ext=".CATPart",
                source_file_path="p5-test/p5-smoke.CATPart", source_file_size=0, source_sha256="0" * 64,
            ))
            session.add(ComponentBuild(id=build_id, component_id="P5-SMOKE", component_name="P5 smoke",
                                       component_type="test", cad_model_id=model_id, cad_revision_id=revision_id))
            await session.commit()
            result = await publish_native_capture(CadRepository(session), revision_id, bundle)
            assert result["native_evidence_storage"]["counts"] == {
                "pmi_entities": 2, "pmi_associations": 2, "fta_semantics": 2}
            service = ComponentBuildService(SqlAlchemyComponentBuildRepository(session),
                                            source_status_reader=SqlAlchemySourceStatusReader(session))
            first = await service.list_mbd_annotations(build_id, offset=0, limit=1)
            second = await service.list_mbd_annotations(build_id, offset=1, limit=1)
            assert first["total"] == second["total"] == 2
            assert first["has_more"] is True and second["has_more"] is False
            filtered = await service.list_mbd_annotations(build_id, offset=0, limit=10,
                                                            annotation_kind="roughness")
            assert filtered["total"] == 1 and filtered["records"][0]["fta_semantic_id"] == "A2"
            by_alias = await service.list_mbd_annotations(build_id, offset=0, limit=10, search="孔径")
            assert by_alias["total"] == 1 and by_alias["records"][0]["fta_semantic_id"] == "A1"
            by_view = await service.list_mbd_annotations(build_id, offset=0, limit=10, view_id="V1")
            assert by_view["total"] == 1 and by_view["records"][0]["fta_semantic_id"] == "A1"
            detail = await service.get_mbd_annotation_detail(build_id, "A1")
            assert detail["annotation"]["semantic_payload"]["raw_fields"][0]["raw_value"] == "10"
            assert detail["annotation"]["annotation_ttrs_count"] == 2
            assert detail["native_geometry_status"] == "native_ttrs_unmapped"
            assert {relation["pmi_id"] for relation in detail["relations"]} == {"P1", "V1"}
            assert detail["render_mapping_status"] == "unmapped"
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(ComponentBuild).where(ComponentBuild.id == build_id))
            await cleanup.execute(delete(CadModelRevision).where(CadModelRevision.id == revision_id))
            await cleanup.execute(delete(CadModel).where(CadModel.id == model_id))
            await cleanup.commit()
        await engine.dispose()
