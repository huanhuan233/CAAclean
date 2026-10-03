from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.measurement.service import MeasurementService


@pytest.mark.asyncio
async def test_interactive_result_uses_snapshot_and_does_not_replace_automatic_facts(tmp_path: Path, monkeypatch):
    revision_id = uuid4()
    build_id = uuid4()
    scope_id = uuid4()
    root = tmp_path / str(revision_id) / "feature-center"
    geometry = root / "geometry"
    geometry.mkdir(parents=True)
    (geometry / "FACE1.brep").write_bytes(b"face")
    (geometry / "FACE2.brep").write_bytes(b"face two")
    assets = {name: {"kind": "face", "path": f"geometry/{name}.brep",
                     "sha256": hashlib.sha256((geometry / f"{name}.brep").read_bytes()).hexdigest()}
              for name in ("FACE1", "FACE2")}
    index = {"geometry_snapshot_id": "snap1", "assets": assets}
    index_path = geometry / "index.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({"output_files": {"geometry/index.json": {
        "sha256": hashlib.sha256(index_path.read_bytes()).hexdigest()}}}), encoding="utf-8")
    (root / "parts.jsonl").write_text(json.dumps({"tolerance_mm": 0.01}) + "\n", encoding="utf-8")

    class Repository:
        def __init__(self):
            self.facts = []

        async def get_build_context(self, requested_id):
            assert requested_id == build_id
            return SimpleNamespace(), SimpleNamespace(id=revision_id), SimpleNamespace(id=scope_id)

        async def save_interactive_result(self, fact):
            self.facts.append(fact)

    calls = []

    async def fake_runner(_script, job, _work, _settings):
        calls.append(job)
        return {"status": "success", "values": {"distance_mm": 3.0,
                "nearest_points": [{"a": [0, 0, 0], "b": [3, 0, 0]}]}, "unit": "mm"}

    monkeypatch.setattr("app.measurement.service.run_freecad_job", fake_runner)
    repo = Repository()
    service = MeasurementService(repo)
    request = {"operation": "distance", "references": [
        {"revision_id": str(revision_id), "geometry_snapshot_id": "snap1", "entity_id": "FACE1"},
        {"revision_id": str(revision_id), "geometry_snapshot_id": "snap1", "entity_id": "FACE2"}],
        "parameters": {}, "source_policy": "auxiliary_brep"}
    result = await service.query_geometry(build_id, request, Settings(cad_work_dir=tmp_path))
    assert result["status"] == "success"
    assert result["result_id"] == str(repo.facts[0].id)
    assert repo.facts[0].algorithm_version == "interactive.p1.v1"
    assert repo.facts[0].source_entity_ids == []
    assert len(calls) == 1
    stale = {**request, "references": [{**request["references"][0], "geometry_snapshot_id": "old"}, request["references"][1]]}
    assert (await service.query_geometry(build_id, stale, Settings(cad_work_dir=tmp_path)))["status"] == "stale_reference"
    native = {**request, "source_policy": "native_only"}
    assert (await service.query_geometry(build_id, native, Settings(cad_work_dir=tmp_path)))["status"] == "unsupported"
    assert len(calls) == 1
