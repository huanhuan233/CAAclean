from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


ALGORITHM_VERSION = "phase2.v1"
NAMESPACE = uuid.UUID("3ee8e90d-7b84-42a7-88e3-cad000000002")


@dataclass(frozen=True)
class EntityFact:
    id: uuid.UUID
    revision_id: uuid.UUID
    parent_entity_id: uuid.UUID | None
    entity_type: str
    geometry_type: str | None
    geometry: dict[str, Any]
    center: list[float] | None
    bounding_box: dict[str, Any] | None
    area: float | None
    length: float | None
    source_ref: str | None


@dataclass
class FeatureCandidateFact:
    revision_id: uuid.UUID
    scope_entity_id: uuid.UUID
    feature_type: str
    source_entity_ids: list[uuid.UUID]
    parameters: dict[str, Any]
    axis: list[float] | None
    center: list[float] | None
    confidence: float
    algorithm: str
    algorithm_version: str = ALGORITHM_VERSION
    status: str = "candidate"
    metadata: dict[str, Any] = field(default_factory=dict)
    id: uuid.UUID | None = None


@dataclass
class MeasurementFact:
    revision_id: uuid.UUID
    scope_entity_id: uuid.UUID
    feature_id: uuid.UUID | None
    measurement_type: str
    raw_value: dict[str, Any]
    normalized_value: dict[str, Any]
    unit: str | None
    source_entity_ids: list[uuid.UUID]
    method: str
    confidence: float
    algorithm_version: str = ALGORITHM_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)
    id: uuid.UUID | None = None


@dataclass
class MeasurementBuildResult:
    features: list[FeatureCandidateFact]
    measurements: list[MeasurementFact]


def stable_uuid(revision_id: uuid.UUID, algorithm_version: str, kind: str, payload: Any) -> uuid.UUID:
    stable_payload = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return uuid.uuid5(NAMESPACE, f"{revision_id}:{algorithm_version}:{kind}:{stable_payload}")
