"""Versioned tube engineering results on existing Revision and evidence storage."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assembly.context import AssemblyContextError, step_world_solids
from app.cad.parser_runner import FreeCadParserError, run_freecad_job
from app.cad.repository import CadRepository
from app.core.config import Settings
from app.db.models import CadNativeEvidence, CadNativePropertyFact
from app.measurement.geometry_snapshot import GeometryReferenceError, GeometrySnapshot
from app.measurement.repository import MeasurementRepository


ALGORITHM_VERSION = "tube.geometry.p7c.v2"


def validate_tube_result_scope(result: dict, solids: list, tube_solid_id: str) -> tuple[dict[str, dict], list[dict]]:
    """Reject incomplete or duplicated kernel identities before publishing any result."""
    expected = {item.solid_id for item in solids}
    records = result.get("records")
    clearances = result.get("clearances")
    if not isinstance(records, list) or not isinstance(clearances, list) or result.get("algorithm_version") != ALGORITHM_VERSION:
        raise AssemblyContextError("geometry_result_invalid: tube result scope or version mismatch")
    identities = [row.get("solid_id") for row in records if isinstance(row, dict)]
    if len(identities) != len(records) or len(identities) != len(expected) or set(identities) != expected:
        raise AssemblyContextError("geometry_result_invalid: duplicate, missing or extra solid record")
    targets = expected - {tube_solid_id}
    pairs = [(row.get("tube_solid_id"), row.get("target_solid_id"))
             for row in clearances if isinstance(row, dict)]
    if (len(pairs) != len(clearances) or len(pairs) != len(targets) or
        set(pairs) != {(tube_solid_id, target) for target in targets}):
        raise AssemblyContextError("geometry_result_invalid: duplicate, missing or extra target clearance")
    return dict(zip(identities, records)), clearances


class TubeAnalysisService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.measurements = MeasurementRepository(session)
        self.cad = CadRepository(session)

    async def _context(self, build_id: UUID):
        context = await self.measurements.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        return context[1]

    async def list_candidates(self, build_id: UUID, settings: Settings) -> dict:
        revision = await self._context(build_id)
        snapshot = GeometrySnapshot.from_bundle(
            Path(settings.cad_work_dir) / str(revision.id) / "feature-center", str(revision.id))
        candidate_ids = {str(asset.get("source_object_id")) for asset in snapshot.assets.values()
                         if asset.get("kind") == "solid" and asset.get("source_object_id") and
                         asset.get("coordinate_convention") == "world_placed_step"}
        if not candidate_ids:
            raise AssemblyContextError("instance_geometry_mapping_unavailable: no world-placed solid candidates")
        solids = step_world_solids(snapshot, candidate_ids, minimum_instances=1)
        if len(solids) > 64:
            raise AssemblyContextError("analysis_budget_exceeded: more than 64 scoped solids")
        return {"revision_id": str(revision.id), "geometry_snapshot_id": snapshot.snapshot_id,
                "candidates": [{"instance_id": item.instance_id, "solid_id": item.solid_id,
                                "coordinate_system": "step_world"} for item in solids]}

    async def analyze(self, build_id: UUID, settings: Settings, *, tube_instance_id: str,
                      target_instance_ids: list[str] | None = None, tolerance_mm: float = 0.01) -> dict:
        target_instance_ids = target_instance_ids or []
        if (not tube_instance_id or len(tube_instance_id) > 128 or
            len(target_instance_ids) > 31 or
            any(not value or len(value) > 128 or value == tube_instance_id for value in target_instance_ids) or
            len(set(target_instance_ids)) != len(target_instance_ids)):
            raise AssemblyContextError("invalid_input: one tube and 0-31 distinct targets required")
        if not 0 < tolerance_mm <= settings.geometry_tolerance_max_mm:
            raise AssemblyContextError("invalid_input: tolerance outside geometry budget")
        revision = await self._context(build_id)
        bundle = Path(settings.cad_work_dir) / str(revision.id) / "feature-center"
        snapshot = GeometrySnapshot.from_bundle(bundle, str(revision.id))
        scope_diagnostics: list[dict[str, str]] = []
        solids = step_world_solids(snapshot, {tube_instance_id, *target_instance_ids},
                                   diagnostics=scope_diagnostics, minimum_instances=1 if not target_instance_ids else 2)
        tube_solids = [item for item in solids if item.instance_id == tube_instance_id]
        if len(tube_solids) != 1:
            raise AssemblyContextError("unsupported: tube requires one exactly mapped Solid")
        job = {"solids": [{"solid_id": item.solid_id, "asset_path": item.asset_path} for item in solids],
               "target_tube_solid_id": tube_solids[0].solid_id, "tolerance_mm": tolerance_mm,
               "coordinate_system": "step_world"}
        try:
            with tempfile.TemporaryDirectory(prefix="tube-p7c-", dir=bundle.parent) as work:
                result = await run_freecad_job(Path(settings.cad_script_dir) / "tube_geometry.py",
                                               job, Path(work), settings)
        except FreeCadParserError as exc:
            raise AssemblyContextError("geometry_process_failed: " + str(exc)) from exc
        if result.get("status") != "success":
            raise AssemblyContextError(str(result.get("status") or "failed") + ": " +
                                       str(result.get("diagnostic") or "tube kernel failed"))
        records_by_solid, clearances = validate_tube_result_scope(result, solids, tube_solids[0].solid_id)
        config = {"tube_instance_id": tube_instance_id, "target_instance_ids": sorted(target_instance_ids),
                  "tolerance_mm": tolerance_mm,
                  "assets": {item.solid_id: item.asset_sha256 for item in solids}}
        version_seed = {"revision": str(revision.id), "snapshot": snapshot.snapshot_id,
                        "algorithm": ALGORITHM_VERSION, "config": config}
        version = hashlib.sha256(json.dumps(version_seed, sort_keys=True).encode()).hexdigest()
        common = {"result_version": version, "revision_id": str(revision.id),
                  "geometry_snapshot_id": snapshot.snapshot_id, "algorithm_version": ALGORITHM_VERSION,
                  "source": "derived_geometry", "coordinate_system": "step_world", "tolerance_mm": tolerance_mm}
        stored_records = [{**records_by_solid[item.solid_id], **common, "instance_id": item.instance_id,
                           "path_id": "step:" + item.solid_id} for item in solids]
        by_solid = {item.solid_id: item.instance_id for item in solids}
        stored_clearances = [{**row, **common, "tube_instance_id": tube_instance_id,
                              "target_instance_id": by_solid[row["target_solid_id"]],
                              "clearance_id": hashlib.sha256((version + ":" + row["target_solid_id"]).encode()).hexdigest()[:32]}
                             for row in clearances]
        failed = sum(row.get("status") != "evaluated" for row in clearances)
        unknown = sum(row.get("status") == "evaluated" and row.get("intersection_status") in
                      {"boolean_failed", "indeterminate_zero_distance", "numerically_uncertain_volume"}
                      for row in clearances)
        own_status = "complete" if records_by_solid[tube_solids[0].solid_id].get("status") == "confirmed_straight_hollow_tube" else "partial"
        clearance_status = "not_requested" if not target_instance_ids else "complete" if not failed and not unknown else "partial"
        run = {**common, "config": config, "status": "complete" if own_status == "complete" and clearance_status in {"complete", "not_requested"} else "partial",
               "self_analysis_status": own_status, "installation_clearance_status": clearance_status,
               "execution_status": "finished", "candidate_pair_count": len(clearances),
               "successful_pair_count": len(clearances) - failed - unknown,
               "failed_pair_count": failed, "unknown_pair_count": unknown,
               "scope_diagnostics": scope_diagnostics, "diagnostics": result.get("diagnostics"),
               "kernel": result.get("kernel"), "kernel_version": result.get("kernel_version"),
               "freecad_version": result.get("freecad_version")}
        async with self.cad.native_publish_transaction():
            await self.cad.replace_native_evidence(revision.id,
                                                   {"tube_run": [run], "tube_records": stored_records,
                                                    "tube_clearances": stored_clearances}, replace_all=False)
        return {"run": run, "tube_count": sum(item["status"] == "confirmed_straight_hollow_tube"
                                               for item in stored_records), "clearance_count": len(stored_clearances)}

    async def _published_run(self, build_id: UUID, settings: Settings):
        revision = await self._context(build_id)
        row = await self.session.scalar(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision.id, CadNativeEvidence.kind == "tube_run"))
        if row is None:
            raise AssemblyContextError("analysis_unavailable: no published tube analysis")
        run = dict(row.payload)
        try:
            snapshot = GeometrySnapshot.from_bundle(Path(settings.cad_work_dir) / str(revision.id) / "feature-center",
                                                    str(revision.id))
            run["current_snapshot_status"] = "current" if snapshot.snapshot_id == run.get("geometry_snapshot_id") and all(
                snapshot.assets.get(solid_id, {}).get("sha256") == sha
                for solid_id, sha in run.get("config", {}).get("assets", {}).items()) else "stale"
        except (GeometryReferenceError, OSError, ValueError):
            run["current_snapshot_status"] = "unavailable"
        return revision, run

    async def list_results(self, build_id: UUID, settings: Settings, *, kind: str, offset: int, limit: int) -> dict:
        if kind not in {"tube_records", "tube_clearances"} or offset < 0 or not 1 <= limit <= 200:
            raise AssemblyContextError("invalid_input: tube result page")
        revision, run = await self._published_run(build_id, settings)
        filters = [CadNativeEvidence.revision_id == revision.id, CadNativeEvidence.kind == kind,
                   CadNativeEvidence.payload["result_version"].astext == run["result_version"]]
        total = int(await self.session.scalar(select(func.count()).select_from(CadNativeEvidence).where(*filters)) or 0)
        rows = await self.session.scalars(select(CadNativeEvidence).where(*filters)
                                          .order_by(CadNativeEvidence.ordinal).offset(offset).limit(limit))
        records = [row.payload for row in rows]
        return {"run": run, "records": records, "total": total, "has_more": offset + len(records) < total}

    async def list_native_paths(self, build_id: UUID, *, offset: int, limit: int) -> dict:
        if offset < 0 or not 1 <= limit <= 200:
            raise AssemblyContextError("invalid_input: tube path page")
        revision = await self._context(build_id)
        filters = [CadNativePropertyFact.revision_id == revision.id,
                   CadNativePropertyFact.payload["key"].astext == "tube_bending_geometry"]
        total = int(await self.session.scalar(select(func.count()).select_from(CadNativePropertyFact).where(*filters)) or 0)
        rows = await self.session.scalars(select(CadNativePropertyFact).where(*filters)
                                          .order_by(CadNativePropertyFact.sort_order).offset(offset).limit(limit))
        records = []
        for row in rows:
            try:
                path = json.loads(row.payload["raw_value"])
            except (ValueError, KeyError, TypeError):
                path = {"status": "invalid_persisted_path"}
            records.append({"path_id": "native:" + row.subject_id, "object_id": row.subject_id,
                            "revision_id": str(revision.id), "source": "native_sweep_path",
                            "object_status": "path_candidate_hollow_unverified", "path": path})
        return {"records": records, "total": total, "has_more": offset + len(records) < total}
