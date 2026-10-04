"""Opt-in real PostgreSQL publication of P4 relations and paginated details."""

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
async def test_p4_real_postgres_pagination_and_combined_detail(tmp_path: Path) -> None:
    url = os.environ.get("P3_LIVE_DATABASE_URL")
    freecad = os.environ.get("FREECAD_CMD")
    if not url or not freecad:
        pytest.skip("live PostgreSQL/FreeCAD environment not configured")
    bundle = tmp_path / "bundle"
    built = subprocess.run(
        [sys.executable, "-m", "scripts.feature_center", "build", "--step",
         str(ROOT / "backend/tests/fixtures/p4/boss_rib_distance.stp"), "--output", str(bundle)],
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
        capture_output=True, text=True, timeout=90,
    )
    assert built.returncode == 0, built.stderr
    model_id, revision_id, build_id = uuid4(), uuid4(), uuid4()
    engine = create_async_engine(url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            session.add(CadModel(id=model_id, name="P4 integration smoke"))
            await session.flush()
            session.add(CadModelRevision(
                id=revision_id, model_id=model_id, revision_no=1,
                source_file_name="boss_rib_distance.stp", source_file_ext=".stp",
                source_file_path="p4-test/boss_rib_distance.stp", source_file_size=0,
                source_sha256="0"*64,
            ))
            await session.flush()
            session.add(ComponentBuild(
                id=build_id, component_id="P4-SMOKE", component_name="P4 smoke",
                component_type="test", cad_model_id=model_id, cad_revision_id=revision_id,
            ))
            await session.commit()
            counts = await publish_feature_evidence(CadRepository(session), revision_id, bundle)
            assert counts["canonical_features"] == 3
            service = ComponentBuildService(SqlAlchemyComponentBuildRepository(session),
                                            source_status_reader=SqlAlchemySourceStatusReader(session))
            first = await service.get_native_evidence(build_id, "canonical_features", 0, 2)
            second = await service.get_native_evidence(build_id, "canonical_features", 2, 2)
            assert first["total"] == second["total"] == 3
            records = first["records"] + second["records"]
            assert len({item["feature_center_id"] for item in records}) == 3
            rib_id = next(item["feature_center_id"] for item in records if item["family"] == "rib")
            detail = await service.get_recognized_feature_detail(build_id, rib_id)
            assert detail["feature"]["review_state"] == "needs_review"
            assert any(item["name"] == "boss_to_rib_shortest_distance" and item["value"] == 20
                       for item in detail["measurements"])
            assert detail["feature"]["typed_payload"]["geometry_recognition"]["combined_measurements"][0]["status"] == "measured"
            relation = detail["feature"]["typed_payload"]["geometry_recognition"]["combined_measurements"][0]
            assert relation["within_tolerance"] is False
            assert relation["intersection_status"] == "not_evaluated"
            assert detail["feature"]["typed_payload"]["geometry_recognition"]["combined_measurement_status"] == "complete"
            assert detail["feature"]["typed_payload"]["geometry_recognition"]["combined_measurement_diagnostics"]["unevaluated_count"] == 0
            assert next(item for item in detail["measurements"] if item["name"] == "boss_to_rib_shortest_distance")["algorithm_version"] == "p4c_combined.v2"
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(ComponentBuild).where(ComponentBuild.id == build_id))
            await cleanup.execute(delete(CadModelRevision).where(CadModelRevision.id == revision_id))
            await cleanup.execute(delete(CadModel).where(CadModel.id == model_id))
            await cleanup.commit()
        await engine.dispose()
