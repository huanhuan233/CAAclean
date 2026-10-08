"""Resolve trustworthy imported-object scopes from one published STEP snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.measurement.geometry_snapshot import GeometrySnapshot
from app.measurement.geometry_snapshot import transform_geometry


class AssemblyContextError(ValueError):
    pass


@dataclass(frozen=True)
class InstanceSolid:
    instance_id: str
    solid_id: str
    asset_path: str
    asset_sha256: str
    coordinate_convention: str


def resolve_occurrence_matrix(occurrence: dict, parent_world: list[list[float]] | None = None) -> list[list[float]]:
    """CATIMovable absolute matrices are never multiplied by an ancestor matrix."""
    flat = occurrence.get("transform_4x4")
    status = occurrence.get("transform_status")
    if not isinstance(flat, list) or len(flat) != 16:
        raise AssemblyContextError("transform_unavailable: 4x4 occurrence matrix missing")
    matrix = [flat[row * 4:(row + 1) * 4] for row in range(4)]
    try:
        transform_geometry([0, 0, 0], matrix, "point")
    except (ValueError, TypeError, OverflowError) as exc:
        raise AssemblyContextError("transform_invalid: " + str(exc)) from exc
    if status == "resolved_absolute":
        return matrix
    if status != "resolved_parent_relative" or parent_world is None:
        raise AssemblyContextError("transform_unavailable: relative transform has no verified parent")
    composed = [[sum(parent_world[row][k] * matrix[k][column] for k in range(4))
                 for column in range(4)] for row in range(4)]
    try:
        transform_geometry([0, 0, 0], composed, "point")
    except (ValueError, TypeError, OverflowError) as exc:
        raise AssemblyContextError("transform_invalid: " + str(exc)) from exc
    return composed


def step_world_solids(snapshot: GeometrySnapshot, selected_ids: set[str] | None = None,
                      diagnostics: list[dict[str, str]] | None = None,
                      minimum_instances: int = 2) -> list[InstanceSolid]:
    """STEP imported objects are already world placed; CATProduct occurrences are not inferred."""
    records: list[InstanceSolid] = []
    for solid_id, asset in sorted(snapshot.assets.items()):
        if asset.get("kind") != "solid":
            continue
        object_id = str(asset.get("source_object_id") or "")
        if selected_ids is not None and not object_id:
            if diagnostics is not None:
                diagnostics.append({"solid_id": solid_id, "code": "unscoped_identity_unavailable"})
            continue
        if selected_ids is not None and object_id not in selected_ids:
            continue
        if not object_id or asset.get("coordinate_convention") != "world_placed_step":
            raise AssemblyContextError("instance_geometry_mapping_unavailable: reparse selected STEP object with world-placed provenance")
        reference: dict[str, Any] = {"revision_id": snapshot.revision_id,
                                     "geometry_snapshot_id": snapshot.snapshot_id, "entity_id": solid_id}
        records.append(InstanceSolid(object_id, solid_id, str(snapshot.resolve(reference)),
                                     str(asset["sha256"]), "world_placed_step"))
    if selected_ids is not None and selected_ids - {record.instance_id for record in records}:
        raise AssemblyContextError("instance_geometry_mapping_unavailable: selected instance has no exact solid")
    if minimum_instances not in {1, 2}:
        raise AssemblyContextError("invalid_input: minimum instance scope")
    if len({record.instance_id for record in records}) < minimum_instances:
        raise AssemblyContextError(
            f"instance_geometry_mapping_unavailable: at least {minimum_instances} distinct imported objects required")
    if len(records) > 64:
        raise AssemblyContextError("analysis_budget_exceeded: more than 64 scoped solids")
    return records
