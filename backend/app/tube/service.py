# 导管结果接通层：复用几何快照和隔离内核任务，负责范围校验、持久化及分页查询。
# 原生设计引用与辅助内核测量分别保存；重算失败时不发布半成品替换上一可用版本。

"""Versioned tube engineering results on existing Revision and evidence storage."""

from __future__ import annotations

import hashlib
import json
import math
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


ALGORITHM_VERSION = "tube.geometry.circular.v3"
CONFIRMED_TUBE_STATUSES = {"confirmed_straight_hollow_tube", "confirmed_bent_hollow_tube"}


# 发布前检查确认结果的尺寸、单位和截面样本一致性；它是数据契约校验，不重做几何识别。
def validate_tube_dimensions(record: dict) -> None:
    """A confirmed classification must carry usable, consistent measurements."""
    if record.get("status") not in CONFIRMED_TUBE_STATUSES:
        return
    section, path = record.get("section"), record.get("path")
    if not isinstance(section, dict) or not isinstance(path, dict):
        raise AssemblyContextError("geometry_result_invalid: confirmed tube dimensions missing")
    # 仅允许有限正数；显式排除 Python 中同时属于整数类型的布尔值。
    def positive(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0

    outer, inner, wall = (section.get(key) for key in ("outer_diameter_mm", "inner_diameter_mm", "wall_thickness_mm"))
    tolerance = section.get("tolerance_mm")
    samples, segments = section.get("samples"), path.get("segments")
    if (not all(positive(v) for v in (outer, inner, wall, tolerance, path.get("length_mm"))) or
            tolerance > 0.1 or outer <= inner or abs((outer - inner) / 2 - wall) > tolerance or
            section.get("unit") != "mm" or section.get("uniformity_status") != "verified_analytic_constant_section" or
            not isinstance(segments, list) or not segments or
            any(not isinstance(item, dict) or item.get("kind") not in {"line", "arc"} for item in segments) or
            not isinstance(samples, list) or len(samples) != 3 * len(segments)):
        raise AssemblyContextError("geometry_result_invalid: inconsistent confirmed tube section")
    for sample in samples:
        if not isinstance(sample, dict) or sample.get("status") != "verified" or any(
            not positive(sample.get(key)) or abs(sample[key] - expected) > 2 * tolerance
            for key, expected in (("outer_diameter_mm", outer), ("inner_diameter_mm", inner), ("wall_thickness_mm", wall))
        ):
            raise AssemblyContextError("geometry_result_invalid: tube section sample invalid")
    if record["status"] == "confirmed_bent_hollow_tube" and not any(item.get("kind") == "arc" for item in segments):
        raise AssemblyContextError("geometry_result_invalid: bent tube has no bend")


# 按真实 solid_id 和导管/目标对核对输出全集，拒绝重复、漏项、额外对象和算法版本不符。
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
    for record in records:
        validate_tube_dimensions(record)
    targets = expected - {tube_solid_id}
    pairs = [(row.get("tube_solid_id"), row.get("target_solid_id"))
             for row in clearances if isinstance(row, dict)]
    if (len(pairs) != len(clearances) or len(pairs) != len(targets) or
        set(pairs) != {(tube_solid_id, target) for target in targets}):
        raise AssemblyContextError("geometry_result_invalid: duplicate, missing or extra target clearance")
    return dict(zip(identities, records)), clearances


# 串联当前 Revision、世界坐标 Solid、内核作业与既有证据表，不依赖本机 HTTP 回调。
class TubeAnalysisService:
    # 复用同一数据库会话下的测量和 CAD Repository，保持结果发布的事务一致性。
    def __init__(self, session: AsyncSession):
        self.session = session
        self.measurements = MeasurementRepository(session)
        self.cad = CadRepository(session)

    # 从构建记录获取实际 Revision；构建或版本不存在时让路由返回明确的 404。
    async def _context(self, build_id: UUID):
        context = await self.measurements.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        return context[1]

    # 只提供当前快照中具备来源对象和 world_placed_step 坐标约定的实体。
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

    # 限定一个导管实例和可选邻近目标，一次加载后同时计算截面、路径及所请求的间隙。
    # 通过身份与尺寸检查后才生成版本摘要并事务发布；原生证据通道不参与替换。
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
        # 算法、容差、对象范围或资产内容变化都会改变结果版本，避免把旧测量套到新模型上。
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
        own_status = "complete" if records_by_solid[tube_solids[0].solid_id].get("status") in CONFIRMED_TUBE_STATUSES else "partial"
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
            # 只替换导管的三个证据通道；replace_all=False 保留 MBD、原生特征等其他来源。
            await self.cad.replace_native_evidence(revision.id,
                                                   {"tube_run": [run], "tube_records": stored_records,
                                                    "tube_clearances": stored_clearances}, replace_all=False)
        return {"run": run, "tube_count": sum(item["status"] in CONFIRMED_TUBE_STATUSES
                                               for item in stored_records), "clearance_count": len(stored_clearances)}

    # 读取上次发布批次，核对快照 ID 及每个 Solid 的资产摘要；旧值可读但状态可能为 stale。
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
            # 无法重新核验快照时仍允许查看历史数值，但不能宣称与当前显示几何一致。
            run["current_snapshot_status"] = "unavailable"
        return revision, run

    # 按发布批次的 result_version 过滤分页数据，防止不同次计算的记录混到同一列表。
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

    # 读取原生属性中的中心线 JSON；即便路径有效，也保持“空心状态未核验”的来源语义。
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
