from __future__ import annotations

import uuid
import json
import tempfile
from pathlib import Path
from typing import Any

from app.cad.parser_runner import FreeCadParserError, run_freecad_job
from app.core.config import Settings
from app.measurement.geometry_snapshot import GeometryReferenceError, GeometrySnapshot, validate_query
from app.measurement.schemas import MeasurementFact, stable_uuid

from app.measurement.fact_builder import build_measurement_facts
from app.measurement.repository import MeasurementRepository
from app.measurement.schemas import ALGORITHM_VERSION


class MeasurementService:
    def __init__(self, repository: MeasurementRepository, algorithm_version: str = ALGORITHM_VERSION):
        self.repository = repository
        self.algorithm_version = algorithm_version

    async def geometry_context(self, build_id: uuid.UUID, settings: Settings) -> dict:
        context = await self.repository.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        _build, revision, _root = context
        bundle_root = Path(settings.cad_work_dir) / str(revision.id) / "feature-center"
        snapshot = GeometrySnapshot.from_bundle(bundle_root, str(revision.id))
        return {"revision_id": str(revision.id), "geometry_snapshot_id": snapshot.snapshot_id,
                "source": "auxiliary_brep", "asset_count": len(snapshot.assets),
                "available_operations": ["detail", "distance", "angle", "section", "local_thickness"]}

    async def query_geometry(self, build_id: uuid.UUID, request: dict[str, Any], settings: Settings) -> dict:
        operation = str(request.get("operation") or "")
        references = request.get("references") or []
        parameters = request.get("parameters") or {}
        policy = request.get("source_policy") or "auxiliary_brep"
        try:
            validate_query(operation, references, parameters, policy)
        except ValueError as exc:
            code, _, message = str(exc).partition(":")
            return {"status": code, "values": None, "diagnostic": message.strip()}
        context = await self.repository.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        _build, revision, root_entity = context
        bundle_root = Path(settings.cad_work_dir) / str(revision.id) / "feature-center"
        try:
            snapshot = GeometrySnapshot.from_bundle(bundle_root, str(revision.id))
            paths = [snapshot.resolve(reference) for reference in references]
            kinds = [snapshot.assets[reference["entity_id"]]["kind"] for reference in references]
            if operation == "section" and kinds != ["solid"]:
                raise ValueError("unsupported: section requires solid")
            if operation == "local_thickness":
                if kinds != ["face"]:
                    raise ValueError("unsupported: thickness requires face")
                solid_id = snapshot.assets[references[0]["entity_id"]].get("owning_solid_id")
                if not solid_id:
                    raise GeometryReferenceError("geometry_unavailable: owning solid unknown")
                solid_ref = {**references[0], "entity_id": solid_id}
                solid_ref.pop("asset_sha256", None)
                paths.append(snapshot.resolve(solid_ref))
                kinds.append("solid")
        except (GeometryReferenceError, ValueError) as exc:
            code, _, message = str(exc).partition(":")
            return {"status": code, "values": None, "diagnostic": message.strip()}
        if operation != "detail" and root_entity is None:
            return {"status": "geometry_unavailable", "values": None,
                    "diagnostic": "revision has no persisted scope entity for measurement"}
        tolerance = self._effective_tolerance(bundle_root, settings)
        job = {"operation": operation, "asset_paths": [str(path) for path in paths],
               "asset_kinds": kinds, "parameters": parameters, "tolerance_mm": tolerance}
        try:
            with tempfile.TemporaryDirectory(prefix="geometry-query-", dir=bundle_root.parent) as work:
                result = await run_freecad_job(Path(settings.cad_script_dir) / "measure_geometry.py",
                                               job, Path(work), settings)
        except FreeCadParserError as exc:
            code = "timeout" if "timed out" in str(exc) else "failed"
            result = {"status": code, "values": None, "diagnostic": "FreeCAD query process unavailable"}
        result.update({"revision_id": str(revision.id), "geometry_snapshot_id": snapshot.snapshot_id,
                       "operation": operation, "references": references, "parameters": parameters,
                       "source": "auxiliary_brep", "tolerance_mm": tolerance,
                       "algorithm_version": "interactive.p1.v1", "coordinate_system": "part_local"})
        if operation != "detail":
            fact_id = stable_uuid(revision.id, "interactive.p1.v1", operation, {
                "snapshot": snapshot.snapshot_id, "references": references, "parameters": parameters,
                "tolerance": tolerance})
            fact = MeasurementFact(
                id=fact_id, revision_id=revision.id, scope_entity_id=root_entity.id,
                feature_id=None, measurement_type=operation,
                raw_value=result, normalized_value=result.get("values") or {},
                unit=result.get("unit"), source_entity_ids=[], method="freecad_brep_query",
                confidence=0.0, algorithm_version="interactive.p1.v1",
                metadata={"source": "auxiliary_brep", "status": result["status"],
                          "geometry_snapshot_id": snapshot.snapshot_id, "references": references,
                          "parameters": parameters, "diagnostic": result.get("diagnostic"),
                          "kernel": result.get("kernel"), "kernel_version": result.get("kernel_version"),
                          "tolerance_mm": tolerance},
            )
            await self.repository.save_interactive_result(fact)
            result["result_id"] = str(fact_id)
        return result

    @staticmethod
    def _effective_tolerance(bundle_root: Path, settings: Settings) -> float:
        path = bundle_root / "parts.jsonl"
        try:
            first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            value = float(first.get("tolerance_mm"))
        except (OSError, IndexError, ValueError, TypeError, json.JSONDecodeError):
            value = settings.geometry_tolerance_min_mm
        return max(settings.geometry_tolerance_min_mm, min(value, settings.geometry_tolerance_max_mm))

    async def recompute_revision(self, revision_id: uuid.UUID) -> dict:
        entities = await self.repository.list_entity_facts(revision_id)
        facts = build_measurement_facts(entities)
        for feature in facts.features:
            feature.algorithm_version = self.algorithm_version
            feature.id = None
        for measurement in facts.measurements:
            measurement.algorithm_version = self.algorithm_version
            measurement.id = None
        await self.repository.replace_results(
            revision_id,
            facts.features,
            facts.measurements,
            algorithm_version=self.algorithm_version,
        )
        return {
            "revision_id": revision_id,
            "algorithm_version": self.algorithm_version,
            "feature_count": len(facts.features),
            "measurement_count": len(facts.measurements),
        }
