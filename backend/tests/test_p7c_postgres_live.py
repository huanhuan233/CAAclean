"""Opt-in real FreeCAD and temporary PostgreSQL Revision publication."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings
from app.db.models import CadModel, CadModelRevision, CadNativeEvidence, ComponentBuild
from app.tube.service import TubeAnalysisService


@pytest.mark.asyncio
async def test_tube_run_persists_scoped_clearance_without_touching_other_channels(tmp_path: Path):
    if os.environ.get("P7_LIVE_DB") != "1" or os.environ.get("P7_LIVE_FREECAD") != "1":
        pytest.skip("set P7_LIVE_DB=1 and P7_LIVE_FREECAD=1")
    settings = Settings(cad_work_dir=tmp_path)
    model_id, revision_id, build_id = uuid4(), uuid4(), uuid4()
    bundle = tmp_path / str(revision_id) / "feature-center"
    geometry = bundle / "geometry"
    geometry.mkdir(parents=True)
    fixture = tmp_path / "solids.py"
    fixture.write_text("""
import json, sys
from pathlib import Path
import FreeCAD, Part
job=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
root=Path(job['directory'])
Part.makeCylinder(8,80).cut(Part.makeCylinder(6,80)).exportBrep(str(root/'T.brep'))
Part.makeBox(2,2,20,FreeCAD.Vector(10,-1,30)).exportBrep(str(root/'N.brep'))
Path(job['result_json_path']).write_text('{"status":"success"}',encoding='utf-8')
""", encoding="utf-8")
    await run_freecad_job(fixture, {"directory": str(geometry)}, tmp_path / "fixture-job", settings)
    assets = {}
    for solid_id, object_id in (("T", "TUBE"), ("N", "NEIGHBOR")):
        path = geometry / f"{solid_id}.brep"
        assets[solid_id] = {"kind": "solid", "path": "geometry/" + path.name,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "source_object_id": object_id, "coordinate_convention": "world_placed_step"}
    assets["LEGACY"] = {"kind": "solid", "path": "geometry/missing.brep"}
    index_path = geometry / "index.json"
    index_path.write_text(json.dumps({"geometry_snapshot_id": "SNAP", "assets": assets}), encoding="utf-8")
    (bundle / "manifest.json").write_text(json.dumps({"output_files": {"geometry/index.json": {
        "sha256": hashlib.sha256(index_path.read_bytes()).hexdigest()}}}), encoding="utf-8")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            session.add(CadModel(id=model_id, name="P7C isolated test"))
            await session.flush()
            session.add(CadModelRevision(id=revision_id, model_id=model_id, revision_no=1,
                                         source_file_name="tube.step", source_file_ext=".step",
                                         source_file_path="p7c-test/tube.step", source_file_size=0,
                                         source_sha256="0" * 64))
            session.add(ComponentBuild(id=build_id, component_id="P7C-SMOKE", component_name="P7C smoke",
                                       component_type="test", cad_model_id=model_id, cad_revision_id=revision_id))
            await session.commit()
            service = TubeAnalysisService(session)
            result = await service.analyze(build_id, settings, tube_instance_id="TUBE",
                                           target_instance_ids=["NEIGHBOR"], tolerance_mm=0.01)
            assert result["run"]["status"] == "complete"
            assert result["run"]["scope_diagnostics"] == [
                {"solid_id": "LEGACY", "code": "unscoped_identity_unavailable"}]
            paths = await service.list_results(build_id, settings, kind="tube_records", offset=0, limit=10)
            assert paths["run"]["current_snapshot_status"] == "current"
            assert any(row["status"] == "confirmed_straight_hollow_tube" for row in paths["records"])
            gaps = await service.list_results(build_id, settings, kind="tube_clearances", offset=0, limit=10)
            assert gaps["total"] == 1
            assert gaps["records"][0]["distance_mm"] == pytest.approx(2)
            assert gaps["records"][0]["threshold_status"] == "not_provided"
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(CadNativeEvidence).where(CadNativeEvidence.revision_id == revision_id))
            await cleanup.execute(delete(ComponentBuild).where(ComponentBuild.id == build_id))
            await cleanup.execute(delete(CadModelRevision).where(CadModelRevision.id == revision_id))
            await cleanup.execute(delete(CadModel).where(CadModel.id == model_id))
            await cleanup.commit()
        await engine.dispose()
