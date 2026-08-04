"""Feature Center Bundle 的确定性、事务式文件写出实现。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .contracts import (
    FEATURE_CENTER_ALGORITHM_VERSION,
    FEATURE_CENTER_SCHEMA_VERSION,
    FeatureCenterBundle,
    to_json_data,
)


_JSONL_COLLECTIONS = (
    ("parts.jsonl", "parts", "part_id"),
    ("topology_entities.jsonl", "topology_entities", "entity_id"),
    ("topology_relations.jsonl", "topology_relations", "relation_id"),
    ("observations.jsonl", "observations", "observation_id"),
    ("canonical_features.jsonl", "canonical_features", "feature_center_id"),
    ("feature_geometry_links.jsonl", "feature_geometry_links", "link_id"),
    ("measurements.jsonl", "measurements", "measurement_id"),
    ("diagnostics.jsonl", "diagnostics", "diagnostic_id"),
    ("review_requests.jsonl", "review_requests", "review_request_id"),
    ("readiness_probes.jsonl", "readiness_probes", "probe_id"),
)


# 用途：使用固定 JSON 编码规则序列化一条记录，保证中文不转义且键顺序稳定。
def _json_line(value: Any) -> str:
    return json.dumps(
        to_json_data(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )


# 用途：按指定稳定编号字段写出 JSONL；缺失编号时使用完整记录文本决胜。
def _write_jsonl(path: Path, records: Iterable[Any], id_key: str) -> None:
    normalized = [to_json_data(record) for record in records]
    normalized.sort(key=lambda item: (str(item.get(id_key, "")), _json_line(item)))
    with path.open("w", encoding="utf-8", newline="\n") as output:
        for record in normalized:
            output.write(_json_line(record))
            output.write("\n")


# 用途：计算最终文件的字节大小和 SHA-256，供 Manifest 追溯与完整性校验。
def _file_fingerprint(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {"size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


class FeatureCenterBundleWriter:
    """先写同级临时目录并一次重命名，避免留下半成品结果。"""

    # 用途：写出全部核心 JSONL 与最终 Manifest；正式目录已存在时拒绝覆盖。
    def write(self, bundle: FeatureCenterBundle, output_dir: Path | str) -> Path:
        target = Path(output_dir)
        if target.exists():
            raise FileExistsError(f"Feature Center 输出目录已存在：{target.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
        try:
            for file_name, attribute_name, id_key in _JSONL_COLLECTIONS:
                _write_jsonl(staging / file_name, getattr(bundle, attribute_name), id_key)

            if bundle.lightweight:
                lightweight_dir = staging / "lightweight"
                lightweight_dir.mkdir()
                lightweight_dir.joinpath("model.glb").write_bytes(bundle.lightweight["model_glb"])
                for file_name, key in (
                    ("face_mesh_map.json", "face_mesh_map"),
                    ("feature_mesh_map.json", "feature_mesh_map"),
                ):
                    lightweight_dir.joinpath(file_name).write_text(
                        json.dumps(bundle.lightweight[key], ensure_ascii=False, sort_keys=True,
                                   indent=2, allow_nan=False) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )

            output_files = {
                path.relative_to(staging).as_posix(): _file_fingerprint(path)
                for path in sorted(staging.rglob("*"), key=lambda item: item.as_posix())
                if path.is_file()
            }
            manifest = {
                "schema_version": FEATURE_CENTER_SCHEMA_VERSION,
                "algorithm_version": FEATURE_CENTER_ALGORITHM_VERSION,
                "input": {
                    "file_name": Path(bundle.input_file_name).name,
                    "sha256": bundle.input_sha256,
                    "absolute_path_included": False,
                },
                "step": {"sha256": bundle.step_sha256},
                "brep": {"shape_hash": bundle.shape_hash},
                "unit": bundle.unit,
                "coordinate_system": bundle.coordinate_system,
                "runtime": bundle.runtime,
                "algorithms": bundle.algorithms,
                "vision": {"enabled": bundle.vision_enabled, "call_count": 0},
                "degraded": bundle.degraded,
                "feature_recognition_scope": bundle.feature_recognition_scope,
                "performance": bundle.performance,
                "lightweight": {
                    "primitive_count": bundle.lightweight.get("primitive_count", 0),
                    "vertex_count": bundle.lightweight.get("vertex_count", 0),
                    "triangle_count": bundle.lightweight.get("triangle_count", 0),
                    "mapping_strategy": "one_face_one_primitive",
                },
                "output_files": output_files,
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2,
                           allow_nan=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            validation_errors = validate_bundle(staging)
            if validation_errors:
                raise ValueError(
                    "FC_BUNDLE_STAGING_INVALID：" + ";".join(validation_errors)
                )
            os.replace(staging, target)
            return target
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise


# 用途：读取 JSONL 并把语法错误转换为带文件名的 Bundle 校验问题。
def _read_jsonl_for_validation(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                records.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"BUNDLE_JSON_INVALID:{path.name}:{exc}")
    return records


# 用途：校验清单哈希、Schema 和跨文件引用；返回全部问题供 CLI 决定非零退出。
def validate_bundle(bundle_dir: Path | str) -> list[str]:
    root = Path(bundle_dir)
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["BUNDLE_MANIFEST_MISSING"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"BUNDLE_MANIFEST_INVALID:{exc}"]
    if manifest.get("schema_version") != FEATURE_CENTER_SCHEMA_VERSION:
        errors.append("BUNDLE_SCHEMA_INCOMPATIBLE")
    required_files = {file_name for file_name, _, _ in _JSONL_COLLECTIONS}
    manifest_files = set(manifest.get("output_files", {}))
    for file_name in sorted(required_files - manifest_files):
        errors.append(f"BUNDLE_REQUIRED_FILE_UNDECLARED:{file_name}")
    for file_name, expected in manifest.get("output_files", {}).items():
        path = root / file_name
        if not path.is_file():
            errors.append(f"BUNDLE_FILE_MISSING:{file_name}")
            continue
        actual = _file_fingerprint(path)
        if actual != expected:
            errors.append(f"BUNDLE_HASH_MISMATCH:{file_name}")

    parts = _read_jsonl_for_validation(root / "parts.jsonl", errors)
    topology = _read_jsonl_for_validation(root / "topology_entities.jsonl", errors)
    topology_relations = _read_jsonl_for_validation(root / "topology_relations.jsonl", errors)
    observations = _read_jsonl_for_validation(root / "observations.jsonl", errors)
    canonical = _read_jsonl_for_validation(root / "canonical_features.jsonl", errors)
    links = _read_jsonl_for_validation(root / "feature_geometry_links.jsonl", errors)
    measurements = _read_jsonl_for_validation(root / "measurements.jsonl", errors)
    part_ids = {item.get("part_id") for item in parts}
    entity_ids = {item.get("entity_id") for item in topology}
    observation_ids = {item.get("observation_id") for item in observations}
    feature_ids = {item.get("feature_center_id") for item in canonical}
    for relation in topology_relations:
        relation_id = relation.get("relation_id", "unknown")
        for field_name in ("source_entity_id", "target_entity_id"):
            if relation.get(field_name) not in entity_ids:
                errors.append(f"BUNDLE_TOPOLOGY_REFERENCE_MISSING:{relation_id}:{field_name}")
    for observation in observations:
        observation_id = observation.get("observation_id", "unknown")
        if observation.get("part_id") not in part_ids:
            errors.append(f"BUNDLE_PART_REFERENCE_MISSING:{observation_id}")
        for face_id in observation.get("geometry_refs", {}).get("face_ids", []):
            if face_id not in entity_ids:
                errors.append(f"BUNDLE_OBSERVATION_FACE_MISSING:{observation_id}:{face_id}")
    for feature in canonical:
        feature_id = feature.get("feature_center_id", "unknown")
        if feature.get("part_id") not in part_ids:
            errors.append(f"BUNDLE_PART_REFERENCE_MISSING:{feature_id}")
        for face_id in feature.get("geometry_refs", {}).get("face_ids", []):
            if face_id not in entity_ids:
                errors.append(f"BUNDLE_FACE_REFERENCE_MISSING:{feature_id}:{face_id}")
        for observation_id in feature.get("source_observation_ids", []):
            if observation_id not in observation_ids:
                errors.append(f"BUNDLE_OBSERVATION_REFERENCE_MISSING:{feature_id}:{observation_id}")
    for link in links:
        link_id = link.get("link_id", "unknown")
        if link.get("feature_center_id") not in feature_ids:
            errors.append(f"BUNDLE_LINK_FEATURE_MISSING:{link_id}")
        if link.get("face_id") not in entity_ids:
            errors.append(f"BUNDLE_LINK_FACE_MISSING:{link_id}")
    for measurement in measurements:
        measurement_id = measurement.get("measurement_id", "unknown")
        if measurement.get("feature_center_id") not in feature_ids:
            errors.append(f"BUNDLE_MEASUREMENT_FEATURE_MISSING:{measurement_id}")
        for face_id in measurement.get("input_face_ids", []):
            if face_id not in entity_ids:
                errors.append(f"BUNDLE_MEASUREMENT_FACE_MISSING:{measurement_id}:{face_id}")
    face_map_path = root / "lightweight" / "face_mesh_map.json"
    feature_map_path = root / "lightweight" / "feature_mesh_map.json"
    if face_map_path.is_file() and feature_map_path.is_file():
        try:
            face_map = json.loads(face_map_path.read_text(encoding="utf-8"))
            feature_map = json.loads(feature_map_path.read_text(encoding="utf-8"))
            if face_map.get("shape_hash") != manifest.get("brep", {}).get("shape_hash"):
                errors.append("BUNDLE_FACE_MESH_SHAPE_HASH_MISMATCH")
            if feature_map.get("shape_hash") != manifest.get("brep", {}).get("shape_hash"):
                errors.append("BUNDLE_FEATURE_MESH_SHAPE_HASH_MISMATCH")
            for face_id in face_map.get("faces", {}):
                if face_id not in entity_ids:
                    errors.append(f"BUNDLE_FACE_MESH_FACE_MISSING:{face_id}")
            primitive_to_face = face_map.get("primitive_to_face", {})
            declared_primitive_ids = set(primitive_to_face)
            for face_id, mapping in face_map.get("faces", {}).items():
                primitive_id = mapping.get("mesh_primitive_id")
                if primitive_to_face.get(primitive_id) != face_id:
                    errors.append(f"BUNDLE_FACE_MESH_REVERSE_MISMATCH:{face_id}")
            for primitive_id, face_id in primitive_to_face.items():
                if face_map.get("faces", {}).get(face_id, {}).get("mesh_primitive_id") != primitive_id:
                    errors.append(f"BUNDLE_PRIMITIVE_FACE_REVERSE_MISMATCH:{primitive_id}")
            for feature_id, mapping in feature_map.get("features", {}).items():
                if feature_id not in feature_ids:
                    errors.append(f"BUNDLE_FEATURE_MESH_FEATURE_MISSING:{feature_id}")
                for face_id in mapping.get("face_ids", []):
                    if face_id not in entity_ids:
                        errors.append(f"BUNDLE_FEATURE_MESH_FACE_MISSING:{feature_id}:{face_id}")
                for primitive_id in mapping.get("mesh_primitive_ids", []):
                    if primitive_id not in declared_primitive_ids:
                        errors.append(
                            f"BUNDLE_FEATURE_MESH_PRIMITIVE_MISSING:{feature_id}:{primitive_id}"
                        )
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"BUNDLE_MESH_MAP_INVALID:{exc}")
    return sorted(set(errors))
