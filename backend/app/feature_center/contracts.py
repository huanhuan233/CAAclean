"""Feature Center 的纯数据契约与稳定编号工具。"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


FEATURE_CENTER_SCHEMA_VERSION = "cad_feature_center_v1"
FEATURE_CENTER_ALGORITHM_VERSION = "1.0.0"


# 用途：根据语义组成部分生成固定长度编号；编号只在算法版本与输入语义不变时稳定。
def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256()
    digest.update(FEATURE_CENTER_ALGORITHM_VERSION.encode("utf-8"))
    for part in parts:
        encoded = str(part).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return f"{prefix}{digest.hexdigest()[:16].upper()}"


@dataclass
class GeometryRefs:
    """保存 Observation 或 Canonical Feature 对真实几何实体的引用。"""

    face_ids: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)
    wire_ids: list[str] = field(default_factory=list)
    solid_ids: list[str] = field(default_factory=list)
    mesh_primitive_ids: list[str] = field(default_factory=list)


@dataclass
class Observation:
    """保存单一来源提出的候选或已验证事实，不覆盖其他来源。"""

    observation_id: str
    part_id: str
    source_kind: str
    source_id: str
    source_version: str
    proposed_family: str
    proposed_subtype: str = ""
    geometry_refs: GeometryRefs = field(default_factory=GeometryRefs)
    evidence_refs: list[str] = field(default_factory=list)
    classification_confidence: float = 0.0
    localization_confidence: float = 0.0
    measurement_confidence: float = 0.0
    status: str = "candidate"
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class CanonicalFeature:
    """保存多源融合后的统一特征，同时保留所有来源引用。"""

    feature_center_id: str
    part_id: str
    family: str
    subtype: str
    source_observation_ids: list[str] = field(default_factory=list)
    native_feature_ids: list[str] = field(default_factory=list)
    geometry_refs: GeometryRefs = field(default_factory=GeometryRefs)
    coordinate_frame: dict[str, Any] = field(default_factory=dict)
    typed_payload: dict[str, Any] = field(default_factory=dict)
    relations: list[dict[str, Any]] = field(default_factory=list)
    review_state: str = "needs_review"
    provenance: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class Measurement:
    """保存由 B-Rep 计算的权威测量及其方法、容差和输入面。"""

    measurement_id: str
    feature_center_id: str
    name: str
    value: float | None
    unit: str
    tolerance: float | None
    source: str
    method: str
    algorithm_version: str
    input_face_ids: list[str] = field(default_factory=list)
    validity: str = "valid"


@dataclass
class FeatureCenterBundle:
    """聚合一次 Feature Center 写出所需的全部纯数据集合。"""

    input_file_name: str
    input_sha256: str
    step_sha256: str = ""
    shape_hash: str = ""
    unit: str = "mm"
    coordinate_system: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    algorithms: dict[str, str] = field(default_factory=dict)
    parts: list[dict[str, Any]] = field(default_factory=list)
    topology_entities: list[dict[str, Any]] = field(default_factory=list)
    topology_relations: list[dict[str, Any]] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    canonical_features: list[CanonicalFeature] = field(default_factory=list)
    feature_geometry_links: list[dict[str, Any]] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    review_requests: list[dict[str, Any]] = field(default_factory=list)
    readiness_probes: list[dict[str, Any]] = field(default_factory=list)
    performance: dict[str, Any] = field(default_factory=dict)
    lightweight: dict[str, Any] = field(default_factory=dict)
    vision_enabled: bool = False
    degraded: bool = False
    feature_recognition_scope: str = "native_hole_guided_only"


# 用途：把数据类递归转换为仅含 JSON 基础类型的字典。
def to_json_data(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
