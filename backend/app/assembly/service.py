"""Run bounded assembly relations and atomically publish one revision-scoped result."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assembly.context import AssemblyContextError, step_world_solids
from app.cad.parser_runner import FreeCadParserError, run_freecad_job
from app.cad.repository import CadRepository
from app.core.config import Settings
from app.db.models import CadNativeEvidence
from app.measurement.geometry_snapshot import GeometrySnapshot
from app.measurement.repository import MeasurementRepository


ALGORITHM_VERSION = "assembly.p6c.v2"


class AssemblyAnalysisService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.measurements = MeasurementRepository(session)
        self.cad = CadRepository(session)

    async def analyze(self, build_id: UUID, settings: Settings, *, instance_ids: list[str] | None,
                      candidate_distance_mm: float, tolerance_mm: float,
                      source_policy: str = "auxiliary_brep", minimum_lap_fraction: float = 0.5) -> dict:
        if source_policy == "native_only":
            raise AssemblyContextError("unsupported: native CAA spatial kernel is not implemented")
        if source_policy != "auxiliary_brep":
            raise AssemblyContextError("invalid_input: unknown source policy")
        if len(instance_ids or []) > 64 or any(not item or len(item) > 128 for item in instance_ids or []):
            raise AssemblyContextError("invalid_input: invalid instance scope")
        if not 0 < tolerance_mm <= settings.geometry_tolerance_max_mm or not 0 <= candidate_distance_mm <= 10000:
            raise AssemblyContextError("invalid_input: analysis distance or tolerance outside budget")
        if not 0 < minimum_lap_fraction <= 1:
            raise AssemblyContextError("invalid_input: lap overlap fraction outside (0, 1]")
        context = await self.measurements.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        _, revision, _ = context
        bundle = Path(settings.cad_work_dir) / str(revision.id) / "feature-center"
        snapshot = GeometrySnapshot.from_bundle(bundle, str(revision.id))
        solids = step_world_solids(snapshot, set(instance_ids) if instance_ids else None)
        job = {"instances": [{"instance_id": item.instance_id, "solid_id": item.solid_id,
                              "asset_path": item.asset_path,
                              "coordinate_convention": item.coordinate_convention} for item in solids],
               "candidate_distance_mm": candidate_distance_mm, "tolerance_mm": tolerance_mm,
               "minimum_lap_fraction": minimum_lap_fraction}
        try:
            with tempfile.TemporaryDirectory(prefix="assembly-p6a-", dir=bundle.parent) as work:
                result = await run_freecad_job(Path(settings.cad_script_dir) / "assembly_relations.py",
                                               job, Path(work), settings)
        except FreeCadParserError as exc:
            raise AssemblyContextError("geometry_process_failed: " + str(exc)) from exc
        if result.get("status") != "success":
            raise AssemblyContextError(str(result.get("status") or "failed") + ": " +
                                       str(result.get("diagnostic") or "assembly kernel failed"))
        config = {"candidate_distance_mm": candidate_distance_mm, "tolerance_mm": tolerance_mm,
                  "minimum_lap_fraction": minimum_lap_fraction,
                  "instances": sorted({item.instance_id for item in solids}),
                  "assets": {item.solid_id: item.asset_sha256 for item in solids}}
        version_seed = json.dumps({"revision": str(revision.id), "snapshot": snapshot.snapshot_id,
                                   "algorithm": ALGORITHM_VERSION, "config": config}, sort_keys=True)
        result_version = hashlib.sha256(version_seed.encode("utf-8")).hexdigest()
        relations = []
        for ordinal, record in enumerate(result["relations"]):
            relation_id = hashlib.sha256((result_version + ":" + str(ordinal) + ":" +
                                           record["solid_a"] + ":" + record["solid_b"]).encode("utf-8")).hexdigest()[:32]
            relations.append({**record, "relation_id": relation_id, "result_version": result_version,
                              "revision_id": str(revision.id), "geometry_snapshot_id": snapshot.snapshot_id,
                              "algorithm_version": ALGORITHM_VERSION, "tolerance_mm": tolerance_mm,
                              "coordinate_system": "step_world", "source": "auxiliary_brep"})
        run = {"result_version": result_version, "revision_id": str(revision.id),
               "geometry_snapshot_id": snapshot.snapshot_id, "algorithm_version": ALGORITHM_VERSION,
               "source": "auxiliary_brep", "coordinate_system": "step_world",
               "config": config, "evaluated_pair_count": result["evaluated_pair_count"],
               "excluded_pair_count": result["excluded_pair_count"],
               "diagnostics": result.get("diagnostics"), "kernel": result.get("kernel"),
               "kernel_version": result.get("kernel_version"),
               "freecad_version": result.get("freecad_version"), "status": "complete"}
        # Compute and validate before replacing either channel. Failure leaves the prior run readable.
        async with self.cad.native_publish_transaction():
            await self.cad.replace_native_evidence(revision.id,
                                                   {"assembly_run": [run], "assembly_relations": relations},
                                                   replace_all=False)
        return {"run": run, "relation_count": len(relations)}

    async def derive_boolean(self, build_id: UUID, settings: Settings, *,
                             shell_instance_id: str, other_instance_id: str,
                             operation: str, purpose: str) -> dict:
        if (not shell_instance_id or not other_instance_id or
            shell_instance_id == other_instance_id or operation not in {"union", "intersection", "difference"} or
            not purpose.strip()):
            raise AssemblyContextError("invalid_input: two distinct operands, operation and purpose required")
        context = await self.measurements.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        revision = context[1]
        bundle = Path(settings.cad_work_dir) / str(revision.id) / "feature-center"
        snapshot = GeometrySnapshot.from_bundle(bundle, str(revision.id))
        solids = step_world_solids(snapshot, {shell_instance_id, other_instance_id})
        by_instance = {instance_id: [item for item in solids if item.instance_id == instance_id]
                       for instance_id in (shell_instance_id, other_instance_id)}
        if any(len(items) != 1 for items in by_instance.values()):
            raise AssemblyContextError("unsupported: boolean operands require one exact Solid per instance")
        left, right = (by_instance[shell_instance_id][0], by_instance[other_instance_id][0])
        identity = {"revision_id": str(revision.id), "snapshot_id": snapshot.snapshot_id,
                    "left_instance_id": shell_instance_id, "right_instance_id": other_instance_id,
                    "left_asset_sha256": left.asset_sha256, "right_asset_sha256": right.asset_sha256,
                    "operation": operation, "purpose": purpose.strip(), "algorithm": "assembly.boolean.p6c.v1"}
        result_version = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        try:
            with tempfile.TemporaryDirectory(prefix="assembly-boolean-", dir=bundle.parent) as work:
                temporary = Path(work) / "derived.brep"
                result = await run_freecad_job(Path(settings.cad_script_dir) / "assembly_boolean.py",
                                               {"left_asset_path": left.asset_path,
                                                "right_asset_path": right.asset_path,
                                                "output_asset_path": str(temporary),
                                                "operation": operation}, Path(work), settings)
                if result.get("status") not in {"complete", "empty"}:
                    raise AssemblyContextError(str(result.get("status") or "failed") + ": " +
                                               str(result.get("diagnostic") or "boolean failed"))
                asset = result.get("asset")
                asset_ref = None
                if result["status"] == "complete":
                    if not isinstance(asset, dict) or not temporary.is_file() or hashlib.sha256(temporary.read_bytes()).hexdigest() != asset.get("sha256"):
                        raise AssemblyContextError("asset_invalid: derived B-Rep hash mismatch")
                    destination = bundle / "assembly-derived" / (result_version + ".brep")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    staging = destination.with_suffix(".partial")
                    shutil.copyfile(temporary, staging)
                    os.replace(staging, destination)
                    asset_ref = {"relative_path": str(destination.relative_to(bundle)).replace("\\", "/"),
                                 **asset}
        except FreeCadParserError as exc:
            raise AssemblyContextError("geometry_process_failed: " + str(exc)) from exc
        record = {**identity, "result_version": result_version, "result": result,
                  "asset": asset_ref, "shell_role_status": "request_declared_unverified",
                  "source": "auxiliary_brep", "coordinate_system": "step_world"}
        async with self.cad.native_publish_transaction():
            previous = await self.session.scalars(select(CadNativeEvidence).where(
                CadNativeEvidence.revision_id == revision.id, CadNativeEvidence.kind == "assembly_boolean")
                                                  .order_by(CadNativeEvidence.ordinal))
            history = [row.payload for row in previous if row.payload.get("result_version") != result_version]
            if len(history) >= 100:
                raise AssemblyContextError("analysis_budget_exceeded: boolean history limit reached")
            await self.cad.replace_native_evidence(revision.id, {"assembly_boolean": [*history, record]},
                                                   replace_all=False)
        return record

    async def list_booleans(self, build_id: UUID, *, offset: int, limit: int) -> dict:
        context = await self.measurements.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        filters = [CadNativeEvidence.revision_id == context[1].id,
                   CadNativeEvidence.kind == "assembly_boolean"]
        total = int(await self.session.scalar(select(func.count()).select_from(CadNativeEvidence).where(*filters)) or 0)
        rows = await self.session.scalars(select(CadNativeEvidence).where(*filters)
                                          .order_by(CadNativeEvidence.ordinal).offset(offset).limit(limit))
        records = [row.payload for row in rows]
        return {"records": records, "total": total, "has_more": offset + len(records) < total}

    async def list_relations(self, build_id: UUID, *, offset: int, limit: int,
                             contact_kind: str | None = None) -> dict:
        context = await self.measurements.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        revision_id = context[1].id
        run = await self.session.scalar(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id, CadNativeEvidence.kind == "assembly_run"))
        if run is None:
            raise AssemblyContextError("analysis_unavailable: no published assembly result")
        filters = [CadNativeEvidence.revision_id == revision_id,
                   CadNativeEvidence.kind == "assembly_relations",
                   CadNativeEvidence.payload["result_version"].astext == run.payload["result_version"]]
        if contact_kind:
            filters.append(CadNativeEvidence.payload["contact_kind"].astext == contact_kind)
        total = int(await self.session.scalar(select(func.count()).select_from(CadNativeEvidence).where(*filters)) or 0)
        rows = await self.session.scalars(select(CadNativeEvidence).where(*filters)
                                          .order_by(CadNativeEvidence.ordinal).offset(offset).limit(limit))
        records = [row.payload for row in rows]
        return {"run": run.payload, "records": records, "total": total,
                "has_more": offset + len(records) < total}

    async def relation_detail(self, build_id: UUID, relation_id: str) -> dict:
        if not relation_id or len(relation_id) > 64:
            raise AssemblyContextError("invalid_input: relation ID")
        context = await self.measurements.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        listing = await self.list_relations(build_id, offset=0, limit=1)
        rows = await self.session.scalars(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == context[1].id,
            CadNativeEvidence.kind == "assembly_relations",
            CadNativeEvidence.payload["relation_id"].astext == relation_id,
            CadNativeEvidence.payload["result_version"].astext == listing["run"]["result_version"])
                                          .limit(2))
        records = [row.payload for row in rows]
        if len(records) != 1:
            raise AssemblyContextError("relation_unavailable: missing or duplicate relation")
        return {"run": listing["run"], "relation": records[0]}
