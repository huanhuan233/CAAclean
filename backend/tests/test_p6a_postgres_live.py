"""Opt-in end-to-end FreeCAD -> PostgreSQL -> paged assembly query smoke."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.assembly.service import AssemblyAnalysisService
from app.assembly.context import AssemblyContextError
from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings
from app.db.models import CadModel, CadModelRevision, CadNativeEvidence, ComponentBuild


@pytest.mark.asyncio
async def test_p6a_real_kernel_and_postgres_revision_publish(tmp_path: Path):
    if os.environ.get("P6_LIVE_DB") != "1" or os.environ.get("P6_LIVE_FREECAD") != "1":
        pytest.skip("set P6_LIVE_DB=1 and P6_LIVE_FREECAD=1")
    settings = Settings(cad_work_dir=tmp_path)
    model_id, revision_id, build_id = uuid4(), uuid4(), uuid4()
    bundle = tmp_path / str(revision_id) / "feature-center"
    geometry = bundle / "geometry"
    geometry.mkdir(parents=True)
    fixture = tmp_path / "two_boxes.py"
    fixture.write_text("""
import json, sys
from pathlib import Path
import FreeCAD, Part
job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for name, x in [('S1', 0.0), ('S2', 10.0)]:
    Part.makeBox(10, 10, 10, FreeCAD.Vector(x, 0, 0)).exportBrep(str(Path(job['directory']) / (name + '.brep')))
Path(job['result_json_path']).write_text('{"status":"success"}', encoding='utf-8')
""", encoding="utf-8")
    await run_freecad_job(fixture, {"directory": str(geometry)}, tmp_path / "fixture-job", settings)
    assets = {}
    for index in (1, 2):
        name = f"S{index}"
        path = geometry / (name + ".brep")
        assets[name] = {"kind": "solid", "path": "geometry/" + path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "source_object_id": f"OBJ{index}",
                        "coordinate_convention": "world_placed_step"}
    index_path = geometry / "index.json"
    index_path.write_text(json.dumps({"geometry_snapshot_id": "SNAP", "assets": assets}), encoding="utf-8")
    (bundle / "manifest.json").write_text(json.dumps({"output_files": {"geometry/index.json": {
        "sha256": hashlib.sha256(index_path.read_bytes()).hexdigest()}}}), encoding="utf-8")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            session.add(CadModel(id=model_id, name="P6A isolated test"))
            await session.flush()
            session.add(CadModelRevision(id=revision_id, model_id=model_id, revision_no=1,
                                         source_file_name="boxes.step", source_file_ext=".step",
                                         source_file_path="p6a-test/boxes.step", source_file_size=0,
                                         source_sha256="0" * 64))
            session.add(ComponentBuild(id=build_id, component_id="P6A-SMOKE", component_name="P6A smoke",
                                       component_type="test", cad_model_id=model_id,
                                       cad_revision_id=revision_id))
            await session.commit()
            service = AssemblyAnalysisService(session)
            result = await service.analyze(build_id, settings, instance_ids=None,
                                           candidate_distance_mm=1, tolerance_mm=0.01)
            assert result["relation_count"] == 1
            listing = await service.list_relations(build_id, offset=0, limit=1)
            assert listing["total"] == 1 and listing["records"][0]["contact_kind"] == "face_contact"
            assert listing["records"][0]["actual_contact_area_mm2"] == pytest.approx(100)
            detail = await service.relation_detail(build_id, listing["records"][0]["relation_id"])
            assert detail["relation"]["geometry_snapshot_id"] == "SNAP"
            assert detail["run"]["revision_id"] == str(revision_id)
            with pytest.raises(AssemblyContextError, match="selected instance"):
                await service.analyze(build_id, settings, instance_ids=["OBJ1", "missing"],
                                      candidate_distance_mm=1, tolerance_mm=0.01)
            assert (await service.list_relations(build_id, offset=0, limit=10))["total"] == 1
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(CadNativeEvidence).where(CadNativeEvidence.revision_id == revision_id))
            await cleanup.execute(delete(ComponentBuild).where(ComponentBuild.id == build_id))
            await cleanup.execute(delete(CadModelRevision).where(CadModelRevision.id == revision_id))
            await cleanup.execute(delete(CadModel).where(CadModel.id == model_id))
            await cleanup.commit()
        await engine.dispose()
