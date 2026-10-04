"""Opt-in live PostgreSQL publication and detail query smoke test."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.cad.repository import CadRepository
from app.component_builds.native_persistence import publish_feature_evidence
from app.component_builds.repository import SqlAlchemyComponentBuildRepository
from app.component_builds.service import ComponentBuildService, SqlAlchemySourceStatusReader
from app.db.models import CadModel, CadModelRevision, ComponentBuild


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_real_postgres_feature_publication_and_detail(tmp_path: Path) -> None:
    url = os.environ.get("P3_LIVE_DATABASE_URL")
    freecad = os.environ.get("FREECAD_CMD")
    if not url or not freecad:
        pytest.skip("live PostgreSQL/FreeCAD environment not configured")
    bundle = tmp_path / "bundle"
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}
    built = subprocess.run(
        [sys.executable, "-m", "scripts.feature_center", "build", "--step",
         str(ROOT / "backend/tests/fixtures/p3/through.stp"), "--output", str(bundle)],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=90,
    )
    assert built.returncode == 0, built.stderr
    model_id, revision_id, build_id = uuid4(), uuid4(), uuid4()
    engine = create_async_engine(url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            session.add(CadModel(id=model_id, name="P3 integration smoke"))
            await session.flush()
            session.add(CadModelRevision(
                id=revision_id, model_id=model_id, revision_no=1, source_file_name="through.stp",
                source_file_ext=".stp", source_file_path="p3-test/through.stp",
                source_file_size=0, source_sha256="0"*64,
            ))
            await session.flush()
            session.add(ComponentBuild(
                id=build_id, component_id="P3-SMOKE", component_name="P3 smoke",
                component_type="test", cad_model_id=model_id, cad_revision_id=revision_id,
            ))
            await session.commit()
            counts = await publish_feature_evidence(CadRepository(session), revision_id, bundle)
            assert counts["canonical_features"] == 1
            assert counts["measurements"] >= 2
            service = ComponentBuildService(SqlAlchemyComponentBuildRepository(session),
                                            source_status_reader=SqlAlchemySourceStatusReader(session))
            page = await service.get_native_evidence(build_id, "canonical_features", 0, 1)
            assert page["total"] == 1
            feature_id = page["records"][0]["feature_center_id"]
            detail = await service.get_recognized_feature_detail(build_id, feature_id)
            assert detail["feature"]["subtype"] == "through_hole"
            assert any(item["name"] == "diameter" and item["value"] == 10 for item in detail["measurements"])
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(ComponentBuild).where(ComponentBuild.id == build_id))
            await cleanup.execute(delete(CadModelRevision).where(CadModelRevision.id == revision_id))
            await cleanup.execute(delete(CadModel).where(CadModel.id == model_id))
            await cleanup.commit()
        await engine.dispose()
