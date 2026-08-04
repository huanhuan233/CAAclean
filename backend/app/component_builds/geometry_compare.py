"""同一零件的 STEP 与 CATPart Web 产物几何 Golden 对照。"""

from __future__ import annotations

import json
import math
from pathlib import Path


# 用途：比较两个真实 Feature Center Bundle 的总体范围、主实体和 GLB 可加载性。
def compare_feature_center_bundles(step_bundle: Path, catpart_bundle: Path) -> dict:
    step = _bundle_summary(Path(step_bundle))
    catpart = _bundle_summary(Path(catpart_bundle))
    diagonal = max(_diagonal(step["bounding_box"]), _diagonal(catpart["bounding_box"]))
    tolerance = max(0.01, diagonal * 1e-5)
    differences: list[str] = []
    if not _vectors_close(step["dimensions_mm"], catpart["dimensions_mm"], tolerance):
        differences.append("bounding_box_dimensions")
    if not _vectors_close(step["center_mm"], catpart["center_mm"], tolerance):
        differences.append("bounding_box_center")
    if step["unique_solid_count"] != catpart["unique_solid_count"]:
        differences.append("unique_solid_count")
    elif not _volumes_close(step["unique_solid_volumes_mm3"], catpart["unique_solid_volumes_mm3"]):
        differences.append("unique_solid_volumes")
    if not step["glb_loadable"] or not catpart["glb_loadable"]:
        differences.append("glb_loadable")
    return {
        "schema_version": "part_ingest_geometry_compare_v1",
        "status": "match" if not differences else "mismatch",
        "tolerance_mm": tolerance,
        "differences": differences,
        "step": step,
        "catpart": catpart,
    }


# 用途：读取 Bundle 的确定性结构化文件，并将重复导入对象归并为唯一实体几何。
def _bundle_summary(root: Path) -> dict:
    part_lines = (root / "parts.jsonl").read_text(encoding="utf-8").splitlines()
    if not part_lines:
        raise ValueError("BUNDLE_PARTS_EMPTY")
    bounding_box = json.loads(part_lines[0]).get("bounding_box")
    if not _usable_box(bounding_box):
        raise ValueError("BUNDLE_BOUNDING_BOX_INVALID")
    entities = [
        json.loads(line)
        for line in (root / "topology_entities.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    solids = [item for item in entities if item.get("entity_type") == "solid" and _usable_box(item.get("bounding_box"))]
    diagonal = _diagonal(bounding_box)
    geometry_tolerance = max(0.01, diagonal * 1e-5)
    unique = _deduplicate_solids(solids, geometry_tolerance)
    model_path = root / "lightweight" / "model.glb"
    model_header = model_path.read_bytes()[:4] if model_path.is_file() else b""
    minimum = bounding_box["min"]
    maximum = bounding_box["max"]
    return {
        "bounding_box": bounding_box,
        "dimensions_mm": [maximum[index] - minimum[index] for index in range(3)],
        "center_mm": [(maximum[index] + minimum[index]) / 2.0 for index in range(3)],
        "raw_solid_count": len(solids),
        "unique_solid_count": len(unique),
        "unique_solid_volumes_mm3": sorted(float(item.get("volume") or 0.0) for item in unique),
        "glb_loadable": model_header == b"glTF",
        "glb_size_bytes": model_path.stat().st_size if model_path.is_file() else 0,
    }


# 用途：按体积和实体包围盒聚类，消除 STEP 导入树中同一实体的重复呈现。
def _deduplicate_solids(solids: list[dict], tolerance_mm: float) -> list[dict]:
    unique: list[dict] = []
    for solid in solids:
        duplicate = False
        for existing in unique:
            volume_tolerance = max(0.01, abs(float(existing.get("volume") or 0.0)) * 1e-5)
            if (
                abs(float(solid.get("volume") or 0.0) - float(existing.get("volume") or 0.0)) <= volume_tolerance
                and _vectors_close(solid["bounding_box"]["min"], existing["bounding_box"]["min"], tolerance_mm)
                and _vectors_close(solid["bounding_box"]["max"], existing["bounding_box"]["max"], tolerance_mm)
            ):
                duplicate = True
                break
        if not duplicate:
            unique.append(solid)
    return unique


def _volumes_close(left: list[float], right: list[float]) -> bool:
    return all(abs(a - b) <= max(0.01, abs(a) * 1e-5, abs(b) * 1e-5) for a, b in zip(left, right))


def _vectors_close(left: list[float], right: list[float], tolerance: float) -> bool:
    return len(left) == len(right) and all(abs(float(a) - float(b)) <= tolerance for a, b in zip(left, right))


def _usable_box(box: dict | None) -> bool:
    values = list((box or {}).get("min", [])) + list((box or {}).get("max", []))
    return len(values) == 6 and all(math.isfinite(float(value)) and abs(float(value)) < 1e90 for value in values)


def _diagonal(box: dict) -> float:
    return math.sqrt(sum((float(box["max"][index]) - float(box["min"][index])) ** 2 for index in range(3)))
