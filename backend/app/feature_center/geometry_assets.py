# 将同一次 STEP 导入导出的 B-Rep 子形状绑定到稳定拓扑编号，并生成可校验的几何快照索引。
"""Bind exact B-Rep subshapes exported during the same STEP import to stable topology IDs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .contracts import FeatureCenterBundle
from .topology import StableTopology


# 分块计算导出 B-Rep 文件的 SHA-256，供发布后交互引用检查内容完整性。
def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# 只绑定实际存在且有稳定编号的实体/面/边/顶点资产，并将形状、内核版本和资产哈希纳入快照身份。
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
        # 这里记录 STEP 已放置的场景坐标；source_object_id 只是导入对象标识，不是原生装配实例历史。
        if kind == "solid":
            # STEP importer geometry is already placed in its exported scene.
            # The parent is an imported object, not a CATProduct occurrence.
            assets[stable_id]["source_object_id"] = str(entity.get("parent_entity_id") or "")
            assets[stable_id]["coordinate_convention"] = "world_placed_step"
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
