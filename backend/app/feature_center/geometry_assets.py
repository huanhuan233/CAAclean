"""Bind exact B-Rep subshapes exported during the same STEP import to stable topology IDs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .contracts import FeatureCenterBundle
from .topology import StableTopology


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def attach_geometry_assets(
    bundle: FeatureCenterBundle,
    topology: StableTopology,
    parser_entities: list[dict],
    export_dir: Path,
) -> None:
    assets: dict[str, dict] = {}
    source_paths: dict[str, Path] = {}
    for entity in parser_entities:
        source_id = str(entity["id"])
        stable_id = topology.source_entity_map.get(source_id)
        path = export_dir / f"{source_id}.brep"
        if stable_id is None or not path.is_file():
            continue
        kind = entity.get("entity_type")
        if kind not in {"solid", "face", "edge", "vertex"}:
            continue
        assets[stable_id] = {
            "kind": kind,
            "path": f"geometry/{stable_id}.brep",
            "sha256": _file_digest(path),
        }
        if kind in {"face", "edge", "vertex"}:
            assets[stable_id]["owning_solid_id"] = topology.source_entity_map.get(str(entity.get("parent_entity_id")))
        source_paths[stable_id] = path
    if not assets:
        return
    seed = json.dumps({
        "step_sha256": bundle.step_sha256,
        "shape_hash": bundle.shape_hash,
        "kernel_version": bundle.runtime.get("brep_kernel_version", "unknown"),
        "assets": {key: assets[key]["sha256"] for key in sorted(assets)},
    }, sort_keys=True, separators=(",", ":"))
    bundle.geometry_index = {
        "schema_version": "geometry_snapshot_v1",
        "geometry_snapshot_id": hashlib.sha256(seed.encode("ascii")).hexdigest(),
        "step_sha256": bundle.step_sha256,
        "shape_hash": bundle.shape_hash,
        "kernel": bundle.runtime.get("brep_kernel"),
        "kernel_version": bundle.runtime.get("brep_kernel_version"),
        "mesh_deflection_mm": bundle.runtime.get("mesh_deflection_mm", 0.1),
        "assets": assets,
    }
    bundle.geometry_assets = source_paths
