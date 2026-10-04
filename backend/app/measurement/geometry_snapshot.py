"""Immutable B-Rep references and rigid coordinate conversion for interactive queries."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GeometryReferenceError(ValueError):
    pass


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_query(operation: str, references: list[dict], parameters: dict, source_policy: str) -> str:
    if source_policy == "native_only":
        raise ValueError("unsupported: native P1 geometry kernel is unavailable")
    if source_policy != "auxiliary_brep":
        raise ValueError("invalid_input: unknown source policy")
    expected = {"detail": 1, "distance": 2, "angle": 2, "section": 1, "local_thickness": 1}
    if operation not in expected or len(references) != expected[operation]:
        raise ValueError("invalid_input: operation or reference count")
    if any(not isinstance(ref, dict) or not ref.get("entity_id") for ref in references):
        raise ValueError("invalid_input: entity reference required")
    allowed = {
        "detail": {"point", "seed_point"}, "distance": set(),
        "angle": {"orientation", "point_a", "point_b", "seed_point_a", "seed_point_b"},
        "section": {"origin", "normal"}, "local_thickness": {"point", "seed_point"},
    }
    if set(parameters) - allowed[operation]:
        raise ValueError("invalid_input: unsupported parameter")
    if operation == "angle" and parameters.get("orientation") not in {"directed", "unoriented"}:
        raise ValueError("invalid_input: angle orientation required")
    for field in ("point", "seed_point", "point_a", "point_b", "seed_point_a", "seed_point_b", "origin", "normal"):
        value = parameters.get(field)
        if value is None:
            if field in parameters:
                raise ValueError(f"invalid_input: {field} must be finite XYZ")
            continue
        if not isinstance(value, list) or len(value) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
            raise ValueError(f"invalid_input: {field} must be finite XYZ")
    for exact, seed in (("point", "seed_point"), ("point_a", "seed_point_a"), ("point_b", "seed_point_b")):
        if exact in parameters and seed in parameters:
            raise ValueError("invalid_input: exact point and display seed are mutually exclusive")
    if operation == "section" and (parameters.get("origin") is None or parameters.get("normal") is None or sum(x*x for x in parameters["normal"]) <= 1e-24):
        raise ValueError("invalid_input: section plane incomplete")
    if operation == "local_thickness" and parameters.get("point") is None and parameters.get("seed_point") is None:
        raise ValueError("invalid_input: face point required")
    return operation


@dataclass(frozen=True)
class GeometrySnapshot:
    root: Path
    revision_id: str
    snapshot_id: str
    assets: dict[str, dict[str, Any]]
    mesh_deflection_mm: float = 0.1

    @classmethod
    def from_bundle(cls, root: Path, revision_id: str) -> "GeometrySnapshot":
        index_path = root / "geometry" / "index.json"
        if not index_path.is_file():
            raise GeometryReferenceError("geometry_unavailable: no B-Rep snapshot")
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise GeometryReferenceError("geometry_unavailable: bundle manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        published = (manifest.get("output_files") or {}).get("geometry/index.json") or {}
        if _file_digest(index_path) != published.get("sha256"):
            raise GeometryReferenceError("stale_reference: geometry index differs from published manifest")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        deflection = float(index.get("mesh_deflection_mm", 0.1))
        if not math.isfinite(deflection) or deflection <= 0 or deflection > 1:
            raise GeometryReferenceError("geometry_unavailable: invalid mesh deflection")
        return cls(root, revision_id, str(index["geometry_snapshot_id"]), index["assets"], deflection)

    def resolve(self, reference: dict[str, Any]) -> Path:
        if reference.get("revision_id") != self.revision_id or reference.get("geometry_snapshot_id") != self.snapshot_id:
            raise GeometryReferenceError("stale_reference: revision or snapshot differs")
        entity_id = reference.get("entity_id")
        asset = self.assets.get(entity_id)
        if not asset:
            raise GeometryReferenceError("geometry_unavailable: entity has no B-Rep asset")
        relative = Path(str(asset.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise GeometryReferenceError("geometry_unavailable: invalid asset mapping")
        path = (self.root / relative).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise GeometryReferenceError("geometry_unavailable: asset escapes snapshot") from exc
        if not path.is_file():
            raise GeometryReferenceError("geometry_unavailable: asset missing")
        expected = asset.get("sha256")
        if reference.get("asset_sha256") and reference["asset_sha256"] != expected:
            raise GeometryReferenceError("stale_reference: asset fingerprint differs")
        if _file_digest(path) != expected:
            raise GeometryReferenceError("stale_reference: B-Rep asset changed")
        return path


def transform_geometry(value: list[float], matrix: list[list[float]], kind: str) -> list[float]:
    """Apply an orthonormal, right-handed local-to-world transform to a point/direction."""
    if kind not in {"point", "vector", "normal"}:
        raise ValueError("unknown_coordinate_kind")
    if len(value) != 3 or any(not math.isfinite(float(v)) for v in value):
        raise ValueError("invalid_vector")
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ValueError("invalid_matrix")
    m = [[float(x) for x in row] for row in matrix]
    if any(not math.isfinite(x) for row in m for x in row) or any(abs(m[3][i] - (1.0 if i == 3 else 0.0)) > 1e-9 for i in range(4)):
        raise ValueError("invalid_matrix")
    columns = [[m[r][c] for r in range(3)] for c in range(3)]
    norm = lambda x: sum(v * v for v in x)
    dot = lambda x, y: sum(a * b for a, b in zip(x, y))
    if any(abs(norm(col) - 1.0) > 1e-8 for col in columns) or any(abs(dot(columns[i], columns[j])) > 1e-8 for i in range(3) for j in range(i + 1, 3)):
        raise ValueError("non_rigid_transform")
    det = dot(columns[0], [columns[1][1]*columns[2][2]-columns[1][2]*columns[2][1], columns[1][2]*columns[2][0]-columns[1][0]*columns[2][2], columns[1][0]*columns[2][1]-columns[1][1]*columns[2][0]])
    if det < 0:
        raise ValueError("reflection_unsupported")
    result = [sum(m[r][c] * float(value[c]) for c in range(3)) + (m[r][3] if kind == "point" else 0.0) for r in range(3)]
    if kind == "normal":
        length = math.sqrt(norm(result))
        if length <= 1e-12:
            raise ValueError("zero_normal")
        return [x / length for x in result]
    return result
