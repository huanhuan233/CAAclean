#!/usr/bin/env python3
"""Validate one real CAA parser run against the observed or completion contract.

Standard-library only. Compatible with Python 3.8+ on the CATIA workstation.
The validator never infers PASS from fixture names and never mutates parser output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


@dataclass
class Finding:
    status: str
    code: str
    message: str
    artifact: str = ""


class ValidationError(Exception):
    pass


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            return json.load(stream)
    except Exception as exc:
        raise ValidationError(f"cannot read JSON {path}: {exc}")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValidationError(f"{path}:{line_number} is not a JSON object")
                rows.append(value)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"cannot read JSONL {path}: {exc}")
    return rows


def load_fixture_evidence_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read the manually captured fixture-evidence ledger.

    Parser artifacts must stay strict UTF-8. This file is produced by CATIA-side
    tooling on a Chinese Windows workstation and may be ANSI/GBK, so keep the
    fallback scoped to evidence ingestion only.
    """
    last_error: Optional[Exception] = None
    for encoding in ("utf-8-sig", "gbk", "mbcs"):
        rows: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding=encoding) as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValidationError(f"{path}:{line_number} is not a JSON object")
                    rows.append(value)
            return rows
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except ValidationError:
            raise
        except Exception as exc:
            last_error = exc
            continue
    raise ValidationError(f"cannot read fixture evidence JSONL {path}: {last_error}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def schema_generation(value: str) -> int:
    match = re.search(r"_v(\d+)$", value or "")
    return int(match.group(1)) if match else -1


def row_ids(rows: Iterable[Dict[str, Any]], key: str) -> Set[str]:
    return {str(row.get(key, "")) for row in rows if str(row.get(key, ""))}


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def matrix_apply(matrix: Sequence[float], point: Sequence[float]) -> List[float]:
    return [
        float(matrix[0]) * point[0] + float(matrix[1]) * point[1] + float(matrix[2]) * point[2] + float(matrix[3]),
        float(matrix[4]) * point[0] + float(matrix[5]) * point[1] + float(matrix[6]) * point[2] + float(matrix[7]),
        float(matrix[8]) * point[0] + float(matrix[9]) * point[1] + float(matrix[10]) * point[2] + float(matrix[11]),
    ]


def vector_error(actual: Sequence[float], expected: Sequence[float]) -> float:
    return max(abs(float(a) - float(e)) for a, e in zip(actual, expected))


def determinant3(values: Sequence[float]) -> float:
    return (
        float(values[0]) * (float(values[5]) * float(values[10]) - float(values[6]) * float(values[9]))
        - float(values[1]) * (float(values[4]) * float(values[10]) - float(values[6]) * float(values[8]))
        + float(values[2]) * (float(values[4]) * float(values[9]) - float(values[5]) * float(values[8]))
    )


def rotation_orthogonality_error(matrix: Sequence[float]) -> float:
    rows = [
        [float(matrix[0]), float(matrix[1]), float(matrix[2])],
        [float(matrix[4]), float(matrix[5]), float(matrix[6])],
        [float(matrix[8]), float(matrix[9]), float(matrix[10])],
    ]
    errors: List[float] = []
    for i in range(3):
        for j in range(3):
            dot = sum(rows[i][k] * rows[j][k] for k in range(3))
            errors.append(abs(dot - (1.0 if i == j else 0.0)))
    return max(errors)


def find_fixture(catalog: Dict[str, Any], fixture_id: str) -> Dict[str, Any]:
    for fixture in catalog.get("fixtures", []):
        if fixture.get("id") == fixture_id:
            return fixture
    raise ValidationError(f"fixture id not found in catalog: {fixture_id}")


class RunValidator:
    def __init__(
        self,
        mode: str,
        contract: Dict[str, Any],
        fixture: Dict[str, Any],
        run_dir: Path,
        allow_known_blocked_fixtures: bool = False,
        fixture_evidence: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.mode = mode
        self.contract = contract
        self.fixture = fixture
        self.run_dir = run_dir
        self.allow_known_blocked_fixtures = allow_known_blocked_fixtures
        self.fixture_evidence = fixture_evidence or {}
        self.findings: List[Finding] = []
        self.rows: Dict[str, List[Dict[str, Any]]] = {}
        self.json_docs: Dict[str, Any] = {}

    def add(self, status: str, code: str, message: str, artifact: str = "") -> None:
        self.findings.append(Finding(status, code, message, artifact))

    def check(self, condition: bool, code: str, success: str, failure: str, artifact: str = "") -> None:
        self.add("PASS" if condition else "FAIL", code, success if condition else failure, artifact)

    def load_artifacts(self) -> None:
        for name in self.contract.get("required_artifacts", []):
            path = self.run_dir / name
            if not path.is_file():
                self.add("FAIL", "ARTIFACT_MISSING", f"required artifact is missing: {name}", name)
                continue
            self.add("PASS", "ARTIFACT_PRESENT", f"artifact present: {name}", name)
            try:
                if name.endswith(".jsonl"):
                    self.rows[name] = load_jsonl(path)
                elif name.endswith(".json"):
                    self.json_docs[name] = load_json(path)
            except ValidationError as exc:
                self.add("FAIL", "ARTIFACT_INVALID_JSON", str(exc), name)

    def validate_fields(self) -> None:
        key = "jsonl_required_fields" if self.mode == "baseline" else "target_jsonl_fields"
        for name, fields in self.contract.get(key, {}).items():
            rows = self.rows.get(name)
            if rows is None:
                continue
            missing_examples: List[str] = []
            for index, row in enumerate(rows, 1):
                missing = [field for field in fields if field not in row]
                if missing:
                    missing_examples.append(f"row {index}: {','.join(missing)}")
                    if len(missing_examples) >= 5:
                        break
            self.check(
                not missing_examples,
                "FIELDS_COMPLETE",
                f"all {len(rows)} rows have required fields",
                "; ".join(missing_examples),
                name,
            )

    def validate_manifest(self) -> None:
        manifest = self.json_docs.get("manifest.json")
        if not isinstance(manifest, dict):
            return
        schema = str(manifest.get("schema_version", ""))
        if self.mode == "baseline":
            expected = self.contract.get("source", {}).get("schema_version")
            self.check(schema == expected, "SCHEMA_BASELINE", f"schema is {schema}", f"expected {expected}, got {schema}", "manifest.json")
        else:
            minimum = int(self.contract.get("minimum_schema_generation", 0))
            self.check(schema_generation(schema) >= minimum, "SCHEMA_COMPLETION", f"schema {schema} meets minimum v{minimum}", f"schema {schema!r} must be v{minimum} or later", "manifest.json")

        artifacts = manifest.get("artifacts", {})
        if not isinstance(artifacts, dict):
            self.add("FAIL", "MANIFEST_ARTIFACTS_INVALID", "manifest.artifacts must be an object", "manifest.json")
            return
        for name, metadata in artifacts.items():
            path = self.run_dir / name
            if not path.is_file() or not isinstance(metadata, dict):
                self.add("FAIL", "MANIFEST_ENTRY_INVALID", f"manifest entry cannot be verified: {name}", "manifest.json")
                continue
            expected_hash = str(metadata.get("sha256", "")).lower()
            expected_size = metadata.get("size_bytes")
            actual_hash = sha256(path)
            actual_size = path.stat().st_size
            self.check(expected_hash == actual_hash, "MANIFEST_HASH", f"hash verified for {name}", f"hash mismatch for {name}", name)
            self.check(expected_size == actual_size, "MANIFEST_SIZE", f"size verified for {name}", f"size mismatch for {name}: expected {expected_size}, got {actual_size}", name)

    def validate_coverage(self) -> None:
        coverage = self.json_docs.get("coverage.json")
        if not isinstance(coverage, dict):
            return
        required = ["enumerated_total", "typed_count", "generic_count", "opaque_count", "failed_count"]
        if not all(isinstance(coverage.get(key), int) for key in required):
            self.add("FAIL", "COVERAGE_FIELDS", "coverage counters are missing or non-integer", "coverage.json")
            return
        conserved = coverage["typed_count"] + coverage["generic_count"] + coverage["opaque_count"] + coverage["failed_count"]
        self.check(coverage["enumerated_total"] == conserved, "COVERAGE_CONSERVED", "object coverage is conserved", f"enumerated_total={coverage['enumerated_total']} but terminal sum={conserved}", "coverage.json")
        features = self.rows.get("features.jsonl")
        if features is not None:
            self.check(len(features) == coverage["enumerated_total"], "FEATURE_COUNT_CONSERVED", "features row count matches enumerated_total", f"features rows={len(features)}, enumerated_total={coverage['enumerated_total']}", "features.jsonl")

    def validate_references(self) -> None:
        features = self.rows.get("features.jsonl", [])
        feature_ids = row_ids(features, "feature_id")
        self.check(len(feature_ids) == len(features), "FEATURE_ID_UNIQUE", "feature_id values are unique", "duplicate or empty feature_id", "features.jsonl")
        for row in features:
            parent = str(row.get("parent_id") or "")
            if parent and parent not in feature_ids:
                self.add("FAIL", "FEATURE_PARENT_DANGLING", f"{row.get('feature_id')} -> missing {parent}", "features.jsonl")

        for row in self.rows.get("relations.jsonl", []):
            if str(row.get("from_id", "")) not in feature_ids or str(row.get("to_id", "")) not in feature_ids:
                self.add("FAIL", "RELATION_DANGLING", f"dangling relation {row}", "relations.jsonl")

        body_rows = self.rows.get("native_topology_bodies.jsonl", [])
        body_ids = row_ids(body_rows, "body_id")
        cell_rows = self.rows.get("native_topology_cells.jsonl", [])
        cell_ids = row_ids(cell_rows, "cell_id")
        self.check(len(cell_ids) == len(cell_rows), "CELL_ID_UNIQUE", "cell_id values are unique", "duplicate or empty cell_id", "native_topology_cells.jsonl")
        for row in cell_rows:
            if str(row.get("body_id", "")) not in body_ids:
                self.add("FAIL", "CELL_BODY_DANGLING", f"cell {row.get('cell_id')} has missing body", "native_topology_cells.jsonl")
            for key in ("boundary_cell_ids", "adjacent_cell_ids"):
                for ref in row.get(key, []) or []:
                    if str(ref) not in cell_ids:
                        self.add("FAIL", "CELL_REFERENCE_DANGLING", f"{row.get('cell_id')} {key} -> {ref}", "native_topology_cells.jsonl")

        for row in self.rows.get("native_topology_wires.jsonl", []):
            if str(row.get("body_id", "")) not in body_ids:
                self.add("FAIL", "WIRE_BODY_DANGLING", f"wire {row.get('wire_id')} has missing body", "native_topology_wires.jsonl")
            face = str(row.get("owning_face_id", ""))
            if face and face not in cell_ids:
                self.add("FAIL", "WIRE_FACE_DANGLING", f"wire {row.get('wire_id')} -> {face}", "native_topology_wires.jsonl")
            for edge in row.get("edge_cell_ids", []) or []:
                if str(edge) not in cell_ids:
                    self.add("FAIL", "WIRE_EDGE_DANGLING", f"wire {row.get('wire_id')} -> {edge}", "native_topology_wires.jsonl")

        result_rows = self.rows.get("native_feature_results.jsonl", [])
        result_ids = row_ids(result_rows, "result_id")
        result_cell_rows = self.rows.get("native_feature_result_cells.jsonl", [])
        result_cell_ids = row_ids(result_cell_rows, "result_cell_id")
        for row in result_rows:
            if str(row.get("source_feature_id", "")) not in feature_ids:
                self.add("FAIL", "RESULT_FEATURE_DANGLING", f"result {row.get('result_id')} has missing source feature", "native_feature_results.jsonl")
        for row in result_cell_rows:
            if str(row.get("result_id", "")) not in result_ids:
                self.add("FAIL", "RESULT_CELL_RESULT_DANGLING", f"result cell {row.get('result_cell_id')} has missing result", "native_feature_result_cells.jsonl")
        for row in self.rows.get("native_feature_topology_links.jsonl", []):
            if str(row.get("result_cell_id", "")) not in result_cell_ids:
                self.add("FAIL", "FEATURE_LINK_RESULT_CELL_DANGLING", f"link {row.get('link_id')} has missing result cell", "native_feature_topology_links.jsonl")
            final = str(row.get("final_cell_id", ""))
            if final and final not in cell_ids:
                self.add("FAIL", "FEATURE_LINK_FINAL_CELL_DANGLING", f"link {row.get('link_id')} -> {final}", "native_feature_topology_links.jsonl")
            for candidate in row.get("candidate_final_cell_ids", []) or []:
                if str(candidate) not in cell_ids:
                    self.add("FAIL", "FEATURE_LINK_CANDIDATE_DANGLING", f"link {row.get('link_id')} candidate -> {candidate}", "native_feature_topology_links.jsonl")

        fta_sets = row_ids(self.rows.get("fta_sets.jsonl", []), "fta_set_id")
        fta_semantics = self.rows.get("fta_semantics.jsonl", [])
        semantic_ids = row_ids(fta_semantics, "fta_semantic_id")
        for row in fta_semantics:
            if str(row.get("fta_set_id", "")) not in fta_sets:
                self.add("FAIL", "FTA_SET_DANGLING", f"semantic {row.get('fta_semantic_id')} has missing set", "fta_semantics.jsonl")
        for row in self.rows.get("fta_topology_links.jsonl", []):
            if str(row.get("fta_semantic_id", "")) not in semantic_ids:
                self.add("FAIL", "FTA_LINK_SEMANTIC_DANGLING", f"FTA link {row.get('fta_link_id')} has missing semantic", "fta_topology_links.jsonl")
            final = str(row.get("final_cell_id", ""))
            if final and final not in cell_ids:
                self.add("FAIL", "FTA_LINK_CELL_DANGLING", f"FTA link {row.get('fta_link_id')} -> {final}", "fta_topology_links.jsonl")

        references = self.rows.get("product_references.jsonl", [])
        reference_ids = row_ids(references, "reference_id")
        instances = self.rows.get("product_instances.jsonl", [])
        instance_ids = row_ids(instances, "instance_id")
        for row in instances:
            if str(row.get("reference_id", "")) not in reference_ids:
                self.add("FAIL", "PRODUCT_REFERENCE_DANGLING", f"instance {row.get('instance_id')} has missing reference", "product_instances.jsonl")
            parent = str(row.get("parent_instance_id") or "")
            if parent and parent not in instance_ids:
                self.add("FAIL", "PRODUCT_PARENT_DANGLING", f"instance {row.get('instance_id')} -> missing parent {parent}", "product_instances.jsonl")

    def validate_mesh_ranges(self) -> None:
        rows = self.rows.get("native_mesh_face_map.jsonl", [])
        by_body: Dict[str, List[Tuple[int, int, str]]] = {}
        for row in rows:
            start = row.get("triangle_start")
            count = row.get("triangle_count")
            if not isinstance(start, int) or not isinstance(count, int) or start < 0 or count < 0:
                self.add("FAIL", "MESH_RANGE_INVALID", f"invalid triangle range in {row.get('mesh_map_id')}", "native_mesh_face_map.jsonl")
                continue
            by_body.setdefault(str(row.get("body_id", "")), []).append((start, start + count, str(row.get("mesh_map_id", ""))))
            estimated = row.get("estimated_triangle_count")
            if isinstance(estimated, int) and estimated < 0:
                self.add("FAIL", "MESH_ESTIMATE_INVALID", f"negative estimated count in {row.get('mesh_map_id')}", "native_mesh_face_map.jsonl")
        for body, ranges in by_body.items():
            ranges.sort()
            previous_end = 0
            for start, end, map_id in ranges:
                if start < previous_end:
                    self.add("FAIL", "MESH_RANGE_OVERLAP", f"overlap in body {body} at {map_id}", "native_mesh_face_map.jsonl")
                if self.mode == "completion" and start != previous_end:
                    self.add("FAIL", "MESH_RANGE_GAP", f"non-contiguous range in body {body}: expected {previous_end}, got {start}", "native_mesh_face_map.jsonl")
                previous_end = max(previous_end, end)

    def validate_fixture_expectations(self) -> None:
        native_rows = self.rows.get("native_features.jsonl", [])
        decoded = {str(row.get("canonical_native_type", "")).lower() for row in native_rows if str(row.get("decoder_status", "")) == "decoded"}
        non_decoder_tokens = {"annotation_set", "product_reference", "product_instance", "pattern", "boolean"}
        for expected in self.fixture.get("native_expected", []):
            token = str(expected).lower()
            if token in non_decoder_tokens:
                continue
            self.check(token in decoded, "FIXTURE_NATIVE_EXPECTED", f"decoded native type present: {token}", f"expected decoded native type missing: {token}", "native_features.jsonl")

        package = self.fixture.get("package")
        if package == "fta_mbd" or "fta-change" in self.fixture.get("roles", []):
            semantics = self.rows.get("fta_semantics.jsonl", [])
            self.check(bool(semantics), "FTA_REAL_SEMANTICS", "FTA semantics are non-empty", "FTA fixture produced no semantic records", "fta_semantics.jsonl")
            if self.mode == "completion":
                types = {str(row.get("semantic_type", "")) for row in semantics}
                expected_types = set(self.contract.get("fta_semantic_types", [])) if self.fixture.get("id") == "FTA-SEMANTICS-01" else set()
                missing = sorted(expected_types - types)
                if missing and self.allow_known_blocked_fixtures and self.fixture.get("id") in {"FTA-SEMANTICS-01", "FTA-REFERENCE-01", "FTA-NEGATIVE-01"}:
                    evidence = self.fixture_evidence.get(str(self.fixture.get("file", "")), {})
                    expected_count = int(evidence.get("annotation_count") or 0)
                    if expected_count and len(semantics) >= expected_count:
                        self.add("BLOCKED_FIXTURE_R21", "FTA_TYPE_COVERAGE_BLOCKED_BY_FIXTURE", f"missing frozen native FTA types remain blocked by fixture evidence: {missing}", "fta_semantics.jsonl")
                    else:
                        self.add("FAIL", "FTA_EXISTING_OBJECTS_LOST", f"existing FTA count from evidence is {expected_count}, parser emitted {len(semantics)}", "fta_semantics.jsonl")
                else:
                    self.check(not missing, "FTA_TYPE_COVERAGE", "all required FTA semantic types are present", f"missing FTA semantic types: {missing}", "fta_semantics.jsonl")
                if not self.rows.get("fta_topology_links.jsonl", []):
                    if self.allow_known_blocked_fixtures and self.fixture.get("id") in {"FTA-SEMANTICS-01", "FTA-REFERENCE-01", "FTA-NEGATIVE-01"}:
                        self.add("BLOCKED_FIXTURE_R21", "FTA_TOPOLOGY_LINKS_BLOCKED_BY_FIXTURE", "FTA topology links are unavailable for the frozen partial native FTA fixtures", "fta_topology_links.jsonl")
                    else:
                        self.add("FAIL", "FTA_TOPOLOGY_LINKS", "FTA topology links are empty", "fta_topology_links.jsonl")
                else:
                    self.add("PASS", "FTA_TOPOLOGY_LINKS", "FTA topology links are non-empty", "fta_topology_links.jsonl")

        if package == "catproduct" or "instance-change" in self.fixture.get("roles", []):
            refs = self.rows.get("product_references.jsonl", [])
            instances = self.rows.get("product_instances.jsonl", [])
            self.check(bool(refs) and bool(instances), "PRODUCT_ROWS", "product reference and instance rows are non-empty", "CATProduct produced no reference/instance rows", "product_instances.jsonl")
            for row in instances:
                matrix = row.get("transform_4x4")
                self.check(isinstance(matrix, list) and len(matrix) == 16 and all(finite_number(v) for v in matrix), "PRODUCT_TRANSFORM", f"valid transform for {row.get('instance_id')}", f"invalid 4x4 transform for {row.get('instance_id')}", "product_instances.jsonl")
            if self.fixture.get("id") == "PRODUCT-01":
                counts: Dict[str, int] = {}
                for row in instances:
                    key = str(row.get("reference_id", ""))
                    counts[key] = counts.get(key, 0) + 1
                self.check(any(count >= 2 for count in counts.values()), "PRODUCT_MULTI_INSTANCE", "same reference has multiple instances", "no shared reference across multiple instances", "product_instances.jsonl")

    def validate_capability_consistency(self) -> None:
        capabilities = self.json_docs.get("capabilities.json")
        matrix = self.json_docs.get("capability_matrix.json")
        if not isinstance(capabilities, dict) or not isinstance(matrix, dict):
            return
        matrix_rows = matrix.get("capabilities", [])
        if not isinstance(matrix_rows, list):
            self.add("FAIL", "CAPABILITY_MATRIX_INVALID", "capability_matrix.capabilities must be a list", "capability_matrix.json")
            return
        required_metrics = {
            "required_count", "resolved_count", "history_confirmed_count", "runtime_identity_count",
            "candidate_count", "ambiguous_count", "unmatched_count", "failed_count", "coverage_ratio",
        }
        metrics = capabilities.get("capability_metrics", {})
        for item in matrix_rows:
            if not isinstance(item, dict):
                self.add("FAIL", "CAPABILITY_MATRIX_INVALID", "capability row is not an object", "capability_matrix.json")
                continue
            name = str(item.get("name", ""))
            if not name:
                self.add("FAIL", "CAPABILITY_MATRIX_INVALID", "capability row has empty name", "capability_matrix.json")
                continue
            if name in capabilities:
                self.check(
                    capabilities.get(name) == item.get("status"),
                    "CAPABILITY_STATUS_CONSISTENT",
                    f"{name} status agrees across capability files",
                    f"{name} status mismatch: capabilities={capabilities.get(name)} matrix={item.get('status')}",
                    "capability_matrix.json",
                )
            missing_matrix = sorted(required_metrics - set(item.keys()))
            self.check(not missing_matrix, "CAPABILITY_MATRIX_METRICS", f"{name} matrix metrics present", f"{name} missing matrix metrics: {missing_matrix}", "capability_matrix.json")
            if isinstance(metrics, dict) and isinstance(metrics.get(name), dict):
                for key in required_metrics:
                    if key in item and key in metrics[name]:
                        self.check(
                            item[key] == metrics[name][key],
                            "CAPABILITY_METRICS_CONSISTENT",
                            f"{name}.{key} agrees across capability files",
                            f"{name}.{key} mismatch: capabilities={metrics[name][key]} matrix={item[key]}",
                            "capability_matrix.json",
                        )

    def authoritative_link(self, row: Dict[str, Any]) -> bool:
        authority = str(row.get("authority", ""))
        if authority in {"catia_persistent_naming", "catia_selection_reference", "verified_r21_public_equivalent"}:
            return bool(str(row.get("persistent_reference", "")))
        if authority == "catia_history_result":
            return bool(str(row.get("persistent_reference", "")))
        return False

    def validate_feature_topology_semantics(self) -> None:
        links = self.rows.get("native_feature_topology_links.jsonl", [])
        if not links:
            return
        bad_pointer = [
            row for row in links
            if str(row.get("mapping_method", "")) == "catia_resultout_final_cell_pointer_identity"
            and (
                str(row.get("mapping_status", "")) == "confirmed"
                or str(row.get("authority", "")) == "catia_history_result"
                or str(row.get("relation_kind", "")) == "generated"
            )
        ]
        self.check(not bad_pointer, "POINTER_IDENTITY_NOT_AUTHORITATIVE", "pointer identity is runtime-only evidence", f"pointer identity promoted to history/generated in {len(bad_pointer)} links", "native_feature_topology_links.jsonl")

        geometry_promoted = [
            row for row in links
            if "geometry_fingerprint" in str(row.get("mapping_method", ""))
            and (str(row.get("mapping_status", "")) == "confirmed" or str(row.get("authority", "")) in set(self.contract.get("authoritative_feature_mapping", {}).get("allowed_authority", [])))
        ]
        self.check(not geometry_promoted, "GEOMETRY_CANDIDATE_NOT_AUTHORITATIVE", "geometry matching stays candidate/ambiguous", f"geometry matching promoted in {len(geometry_promoted)} links", "native_feature_topology_links.jsonl")

        persistent_authorities = {"catia_persistent_naming", "catia_selection_reference", "catia_history_result", "verified_r21_public_equivalent"}
        empty_persistent = [
            row for row in links
            if str(row.get("authority", "")) in persistent_authorities
            and str(row.get("mapping_status", "")) == "confirmed"
            and not str(row.get("persistent_reference", ""))
        ]
        self.check(not empty_persistent, "PERSISTENT_REFERENCE_REQUIRED", "persistent authoritative mappings carry references", f"authoritative mapping has empty persistent_reference in {len(empty_persistent)} links", "native_feature_topology_links.jsonl")

        generated_by_final: Dict[str, Set[str]] = {}
        for row in links:
            final = str(row.get("final_cell_id", ""))
            if final and str(row.get("relation_kind", "")) == "generated" and not self.authoritative_link(row):
                generated_by_final.setdefault(final, set()).add(str(row.get("source_feature_id", "")))
        duplicated = {cell: sources for cell, sources in generated_by_final.items() if len(sources) > 1}
        self.check(not duplicated, "MULTI_GENERATED_REQUIRES_HISTORY", "shared final faces are not generated by multiple non-authoritative features", f"{len(duplicated)} final faces have multiple non-authoritative generated sources", "native_feature_topology_links.jsonl")

        capabilities = self.json_docs.get("capabilities.json")
        if isinstance(capabilities, dict) and capabilities.get("native_feature_topology_mapping") == "complete":
            unresolved = [
                row for row in links
                if str(row.get("mapping_status", "")) in {"runtime_matched", "candidate", "ambiguous", "unmatched", "insufficient_result_fingerprint"}
                or str(row.get("authority", "")) == "runtime_cell_identity"
            ]
            self.check(not unresolved, "MAPPING_COMPLETE_HAS_NO_UNRESOLVED", "complete mapping has no runtime/candidate/unmatched records", f"mapping declared complete with {len(unresolved)} unresolved/runtime links", "capabilities.json")
            directions = {str(row.get("mapping_direction", "")) for row in links}
            require_both = bool(self.contract.get("authoritative_feature_mapping", {}).get("require_forward_and_reverse"))
            if require_both:
                self.check({"result_cell_to_final_face", "final_face_to_source_feature"}.issubset(directions), "MAPPING_FORWARD_REVERSE", "forward and reverse mapping directions are present", f"missing required mapping direction(s): {sorted({'result_cell_to_final_face', 'final_face_to_source_feature'} - directions)}", "native_feature_topology_links.jsonl")

    def validate_decoder_semantics(self) -> None:
        rows = self.rows.get("native_features.jsonl", [])
        decoded_without_payload = [
            row for row in rows
            if str(row.get("decoder_status", "")) == "decoded"
            and str(row.get("payload_extraction_status", "")) != "complete"
        ]
        self.check(not decoded_without_payload, "DECODER_DECODED_REQUIRES_PAYLOAD", "decoded records have complete payload extraction", f"{len(decoded_without_payload)} decoded rows lack complete payload extraction", "native_features.jsonl")
        startup_decoded = [
            row for row in rows
            if str(row.get("decoder", "")) == "StartupTypeCanonicalDecoder"
            and str(row.get("decoder_status", "")) == "decoded"
        ]
        self.check(not startup_decoded, "STARTUP_TYPE_IS_TYPE_ONLY", "startup type decoder is type_only", f"{len(startup_decoded)} startup type rows claim decoded payload", "native_features.jsonl")

    def validate_product_numeric_truth(self) -> None:
        if self.fixture.get("id") not in {"PRODUCT-01", "PRODUCT-02"}:
            return
        rows = self.rows.get("product_instances.jsonl", [])
        tolerance = 1.0e-6
        local_point = [10.0, 0.0, 0.0]
        expected: Dict[str, Tuple[List[float], List[float]]] = {}
        if self.fixture.get("id") == "PRODUCT-01":
            expected = {
                "CAA_PRODUCT_MULTI_INSTANCE/PadReference_Instance_A": (
                    [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                    [10.0, 0.0, 0.0],
                ),
                "CAA_PRODUCT_MULTI_INSTANCE/PadReference_Instance_B": (
                    [0, 1, 0, 140, -1, 0, 0, 20, 0, 0, 1, 0, 0, 0, 0, 1],
                    [140.0, 10.0, 0.0],
                ),
            }
        else:
            expected = {
                "CAA_PRODUCT_NESTED/Assembly_Level_1_A/Part1.1": (
                    [1, 0, 0, 45, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                    [55.0, 0.0, 0.0],
                ),
                "CAA_PRODUCT_NESTED/Assembly_Level_1_A/SUBASSEMBLY_B.1": (
                    [1, 0, 0, 0, 0, 1, 0, 80, 0, 0, 1, 0, 0, 0, 0, 1],
                    [10.0, 80.0, 0.0],
                ),
                "CAA_PRODUCT_NESTED/Assembly_Level_1_A/SUBASSEMBLY_B.1/Part1.1": (
                    [0, 1, 0, 20, -1, 0, 0, 80, 0, 0, 1, 35, 0, 0, 0, 1],
                    [20.0, 70.0, 35.0],
                ),
            }

        by_path = {str(row.get("instance_path", "")): row for row in rows}
        for path, (expected_matrix, expected_world) in expected.items():
            row = by_path.get(path)
            if row is None:
                self.add("FAIL", "PRODUCT_EXPECTED_INSTANCE", f"expected instance missing: {path}", "product_instances.jsonl")
                continue
            matrix = row.get("transform_4x4")
            if not (isinstance(matrix, list) and len(matrix) == 16 and all(finite_number(v) for v in matrix)):
                self.add("FAIL", "PRODUCT_TRANSFORM_NUMERIC", f"expected instance has invalid matrix: {path}", "product_instances.jsonl")
                continue
            matrix_error = vector_error([float(v) for v in matrix], expected_matrix)
            world = matrix_apply(matrix, local_point)
            point_error = vector_error(world, expected_world)
            orth_error = rotation_orthogonality_error(matrix)
            det_error = abs(determinant3(matrix) - 1.0)
            last_row_error = vector_error([float(matrix[12]), float(matrix[13]), float(matrix[14]), float(matrix[15])], [0.0, 0.0, 0.0, 1.0])
            self.check(matrix_error <= tolerance, "PRODUCT_TRANSFORM_EXPECTED_MATRIX", f"{path} absolute transform matches fixture truth", f"{path} matrix error={matrix_error}", "product_instances.jsonl")
            self.check(point_error <= tolerance, "PRODUCT_TRANSFORM_POINT_TRUTH", f"{path} local point maps to expected world point", f"{path} point error={point_error}, world={world}, expected={expected_world}", "product_instances.jsonl")
            self.check(orth_error <= tolerance and det_error <= tolerance and last_row_error <= tolerance, "PRODUCT_TRANSFORM_RIGID", f"{path} transform is rigid homogeneous absolute matrix", f"{path} orth={orth_error} det={det_error} last_row={last_row_error}", "product_instances.jsonl")

    def validate_completion(self) -> None:
        if self.mode != "completion":
            return
        capabilities = self.json_docs.get("capabilities.json")
        if isinstance(capabilities, dict):
            for key, expected in self.relevant_completion_rules().items():
                actual = capabilities.get(key)
                self.check(actual == expected, "CAPABILITY_COMPLETE", f"{key}={expected}", f"{key}: expected {expected}, got {actual}", "capabilities.json")

        package = str(self.fixture.get("package", ""))
        roles = set(self.fixture.get("roles", []))
        if package == "catproduct" or "instance-change" in roles:
            registry = self.json_docs.get("decoder_registry.json")
            self.check(isinstance(registry, (dict, list)) and bool(registry), "DECODER_REGISTRY_EXPORT", "decoder registry export is non-empty", "decoder_registry.json is empty or invalid", "decoder_registry.json")
            return
        if package == "fta_mbd" or "fta-change" in roles:
            registry = self.json_docs.get("decoder_registry.json")
            self.check(isinstance(registry, (dict, list)) and bool(registry), "DECODER_REGISTRY_EXPORT", "decoder registry export is non-empty", "decoder_registry.json is empty or invalid", "decoder_registry.json")
            return
        if package in {"gsd_native", "boundary_negative"}:
            registry = self.json_docs.get("decoder_registry.json")
            self.check(isinstance(registry, (dict, list)) and bool(registry), "DECODER_REGISTRY_EXPORT", "decoder registry export is non-empty", "decoder_registry.json is empty or invalid", "decoder_registry.json")
            return

        links = self.rows.get("native_feature_topology_links.jsonl", [])
        mapping = self.contract.get("authoritative_feature_mapping", {})
        confirmed = [row for row in links if row.get("mapping_status") == mapping.get("required_status")]
        self.check(bool(confirmed), "AUTHORITATIVE_MAPPING_PRESENT", "confirmed Feature-Topology links exist", "no confirmed Feature-Topology links", "native_feature_topology_links.jsonl")
        forbidden = set(mapping.get("forbidden_as_authority", []))
        allowed = set(mapping.get("allowed_authority", []))
        for row in confirmed:
            authority = str(row.get("authority", ""))
            method = str(row.get("mapping_method", ""))
            self.check(authority in allowed and authority not in forbidden, "AUTHORITATIVE_MAPPING_SOURCE", f"authoritative source accepted for {row.get('link_id')}", f"non-authoritative source for {row.get('link_id')}: {authority}", "native_feature_topology_links.jsonl")
            self.check(method not in {"geometry_fingerprint", "center_area_match"}, "AUTHORITATIVE_MAPPING_METHOD", f"mapping method accepted for {row.get('link_id')}", f"candidate method cannot confirm mapping: {method}", "native_feature_topology_links.jsonl")

        roles = set(self.fixture.get("roles", []))
        relation_kinds = {str(row.get("relation_kind", "")) for row in confirmed}
        required_relations = {"generated"}
        if "topology-consumption" in roles or "face-disappears" in roles:
            required_relations.update({"modified", "consumed"})
        if "split" in roles or "one-to-many" in roles:
            required_relations.add("split")
        if "merge" in roles or "many-to-one" in roles:
            required_relations.add("merged")
        missing = sorted(required_relations - relation_kinds)
        self.check(not missing, "FEATURE_RELATION_KINDS", "required feature relation kinds are present", f"missing relation kinds for fixture roles: {missing}", "native_feature_topology_links.jsonl")

        registry = self.json_docs.get("decoder_registry.json")
        self.check(isinstance(registry, (dict, list)) and bool(registry), "DECODER_REGISTRY_EXPORT", "decoder registry export is non-empty", "decoder_registry.json is empty or invalid", "decoder_registry.json")

    def relevant_completion_rules(self) -> Dict[str, str]:
        rules = self.contract.get("completion_rules", {})
        package = str(self.fixture.get("package", ""))
        roles = set(self.fixture.get("roles", []))
        keys = ["manufacturing_feature_recognition", "decoder_registry_export"]
        if package == "catproduct" or "instance-change" in roles:
            keys.append("catproduct_instance_extraction")
        elif package == "fta_mbd" or "fta-change" in roles:
            keys.append("fta_extraction")
            if not self.allow_known_blocked_fixtures:
                keys.append("fta_topology_mapping")
        elif package in {"gsd_native", "boundary_negative"}:
            keys.append("native_feature_extraction")
        else:
            keys.extend([
                "native_feature_extraction",
                "topology_extraction",
                "native_feature_topology_mapping",
                "mesh_face_mapping",
            ])
        return {key: rules[key] for key in keys if key in rules}

    def run(self) -> List[Finding]:
        if not self.run_dir.is_dir():
            self.add("FAIL", "RUN_DIRECTORY_MISSING", f"run directory does not exist: {self.run_dir}")
            return self.findings
        self.load_artifacts()
        self.validate_fields()
        self.validate_manifest()
        self.validate_coverage()
        self.validate_references()
        self.validate_mesh_ranges()
        self.validate_fixture_expectations()
        self.validate_capability_consistency()
        self.validate_feature_topology_semantics()
        self.validate_decoder_semantics()
        self.validate_product_numeric_truth()
        self.validate_completion()
        return self.findings


def compare_runs(run_a: Path, run_b: Path, artifacts: Sequence[str]) -> List[Finding]:
    findings: List[Finding] = []
    for name in artifacts:
        a = run_a / name
        b = run_b / name
        if not a.is_file() or not b.is_file():
            findings.append(Finding("FAIL", "DETERMINISM_ARTIFACT_MISSING", f"cannot compare missing artifact: {name}", name))
            continue
        same = sha256(a) == sha256(b)
        findings.append(Finding("PASS" if same else "FAIL", "DETERMINISM_HASH", f"double-run hash {'matches' if same else 'differs'}: {name}", name))
    return findings


def status_from(findings: Sequence[Finding]) -> str:
    if any(item.status == "FAIL" for item in findings):
        return "FAIL"
    if any(item.status == "BLOCKED_FIXTURE_R21" for item in findings):
        return "BLOCKED_FIXTURE_R21"
    if any(item.status == "UNTESTED_NO_FIXTURE" for item in findings):
        return "UNTESTED_NO_FIXTURE"
    if any(item.status == "BLOCKED" for item in findings):
        return "BLOCKED"
    return "PASS"


def write_report(path: Path, fixture: Dict[str, Any], mode: str, findings: Sequence[Finding], run_a: Path, run_b: Optional[Path]) -> Dict[str, Any]:
    report = {
        "fixture_id": fixture.get("id"),
        "mode": mode,
        "status": status_from(findings),
        "run_a": str(run_a),
        "run_b": str(run_b) if run_b else None,
        "counts": {
            "pass": sum(item.status == "PASS" for item in findings),
            "fail": sum(item.status == "FAIL" for item in findings),
            "blocked": sum(item.status == "BLOCKED" for item in findings),
            "blocked_fixture_r21": sum(item.status == "BLOCKED_FIXTURE_R21" for item in findings),
            "untested_no_fixture": sum(item.status == "UNTESTED_NO_FIXTURE" for item in findings),
        },
        "findings": [asdict(item) for item in findings],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "completion"), required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--fixture-id", required=True)
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--allow-known-blocked-fixtures", action="store_true")
    parser.add_argument("--fixture-evidence", type=Path)
    args = parser.parse_args(argv)

    try:
        contract = load_json(args.contract)
        catalog = load_json(args.catalog)
        fixture = find_fixture(catalog, args.fixture_id)
        evidence: Dict[str, Dict[str, Any]] = {}
        if args.fixture_evidence and args.fixture_evidence.is_file():
            for row in load_fixture_evidence_jsonl(args.fixture_evidence):
                file_name = str(row.get("file", ""))
                if file_name:
                    evidence[file_name] = row
        validator = RunValidator(args.mode, contract, fixture, args.run_a, args.allow_known_blocked_fixtures, evidence)
        findings = validator.run()
        if args.run_b:
            deterministic = contract.get("deterministic_artifacts")
            if not deterministic:
                deterministic = [name for name in contract.get("required_artifacts", []) if name.endswith(".jsonl")]
            findings.extend(compare_runs(args.run_a, args.run_b, deterministic))
        report = write_report(args.report, fixture, args.mode, findings, args.run_a, args.run_b)
        print(f"[{report['status']}] {args.fixture_id}: pass={report['counts']['pass']} fail={report['counts']['fail']}")
        allowed_statuses = {"PASS"}
        if args.allow_known_blocked_fixtures:
            allowed_statuses.update({"BLOCKED_FIXTURE_R21", "UNTESTED_NO_FIXTURE"})
        return 0 if report["status"] in allowed_statuses else 1
    except ValidationError as exc:
        finding = Finding("FAIL", "VALIDATOR_INPUT_ERROR", str(exc))
        fixture = {"id": args.fixture_id}
        write_report(args.report, fixture, args.mode, [finding], args.run_a, args.run_b)
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
