"""Opt-in revision publication and paged native connection queries."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.assembly.connections import ConnectionService
from app.cad.repository import CadRepository
from app.core.config import Settings
from app.db.models import CadModel, CadModelRevision, CadNativeEvidence, ComponentBuild


@pytest.mark.asyncio
async def test_p6b_connection_projection_postgres_query():
    if os.environ.get("P6_LIVE_DB") != "1":
        pytest.skip("set P6_LIVE_DB=1")
    engine = create_async_engine(Settings().database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    model_id, revision_id, build_id = uuid4(), uuid4(), uuid4()
    try:
        async with sessions() as session:
            session.add(CadModel(id=model_id, name="P6B isolated test"))
            await session.flush()
            session.add(CadModelRevision(id=revision_id, model_id=model_id, revision_no=1,
                                         source_file_name="connection.CATProduct", source_file_ext=".CATProduct",
                                         source_file_path="p6b-test/connection.CATProduct", source_file_size=0,
                                         source_sha256="0" * 64))
            session.add(ComponentBuild(id=build_id, component_id="P6B-SMOKE", component_name="P6B smoke",
                                       component_type="test", cad_model_id=model_id,
                                       cad_revision_id=revision_id))
            await session.commit()
            repository = CadRepository(session)
            async with repository.native_publish_transaction():
                await repository.replace_native_evidence(revision_id, {
                    "connection_semantics_status": [{"source_channel_status": "captured", "connection_count": 2}],
                    "connection_semantics": [
                        {"connection_id": "CN1", "kind": "fastener", "root_occurrence_id": "O1"},
                        {"connection_id": "CN2", "kind": "seal", "root_occurrence_id": "O2"}],
                }, replace_all=False)
            service = ConnectionService(session)
            page = await service.list(build_id, offset=0, limit=1)
            assert page["total"] == 2 and page["has_more"]
            assert page["records"][0]["connection_id"] == "CN1"
            assert (await service.list(build_id, offset=0, limit=10, kind="seal"))["total"] == 1
            assert (await service.detail(build_id, "CN2"))["connection"]["kind"] == "seal"
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(CadNativeEvidence).where(CadNativeEvidence.revision_id == revision_id))
            await cleanup.execute(delete(ComponentBuild).where(ComponentBuild.id == build_id))
            await cleanup.execute(delete(CadModelRevision).where(CadModelRevision.id == revision_id))
            await cleanup.execute(delete(CadModel).where(CadModel.id == model_id))
            await cleanup.commit()
        await engine.dispose()
