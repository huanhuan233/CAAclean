#!/usr/bin/env python3
"""Evaluate the CAA V1 Phase 1 scoped contract from existing parser runs.

This script is read-only. It does not parse CATIA files, mutate fixtures, or
weaken the full completion contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from validate_caa_outputs import RunValidator, load_json, load_jsonl, schema_generation, status_from


def safe_run_name(fixture_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in fixture_id) + "_A"


def load_fixture(catalog: Dict[str, Any], fixture_id: str) -> Dict[str, Any]:
    for fixture in catalog.get("fixtures", []):
        if fixture.get("id") == fixture_id:
            return fixture
    raise KeyError(f"fixture not found in catalog: {fixture_id}")


def load_capabilities(run_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return load_json(run_dir / "capabilities.json"), load_json(run_dir / "manifest.json")


def count_payload(rows: List[Dict[str, Any]], family: str) -> int:
    family = family.lower()
    total = 0
    for row in rows:
        canonical = str(row.get("canonical_native_type", "")).lower()
        payload_status = str(row.get("payload_extraction_status", ""))
        decoder_status = str(row.get("decoder_status", ""))
        if family in canonical and payload_status == "complete" and decoder_status == "decoded":
            total += 1
    return total


def count_type_only(rows: List[Dict[str, Any]], family: str) -> int:
    family = family.lower()
    total = 0
    for row in rows:
        canonical = str(row.get("canonical_native_type", "")).lower()
        decoder_status = str(row.get("decoder_status", ""))
        payload_status = str(row.get("payload_extraction_status", ""))
        if family in canonical and decoder_status in {"type_only", "not_implemented"} and payload_status != "complete":
            total += 1
    return total


def evaluate_fixture(contract: Dict[str, Any], catalog: Dict[str, Any], results_dir: Path, fixture_id: str) -> Dict[str, Any]:
    fixture = load_fixture(catalog, fixture_id)
    run_dir = results_dir / safe_run_name(fixture_id)
    checks: List[Dict[str, str]] = []
    if not run_dir.is_dir():
        return {"fixture_id": fixture_id, "status": "FAIL", "checks": [{"status": "FAIL", "code": "RUN_MISSING", "message": str(run_dir)}]}

    completion_contract = {
        "minimum_schema_generation": contract.get("minimum_schema_generation", 11),
        "required_artifacts": contract.get("required_artifacts", []),
        "target_jsonl_fields": {},
        "authoritative_feature_mapping": {"require_forward_and_reverse": True},
    }
    validator = RunValidator("baseline", completion_contract, fixture, run_dir)
    validator.load_artifacts()
    validator.validate_manifest()
    validator.validate_capability_consistency()
    validator.validate_feature_topology_semantics()
    validator.validate_decoder_semantics()
    validator.validate_brep_capability_semantics()
    validator.validate_mesh_mapping_capability_semantics()
    validator.validate_product_capability_semantics()
    validator.validate_product_numeric_truth()
    for finding in validator.findings:
        if finding.status == "FAIL":
            checks.append({"status": "FAIL", "code": finding.code, "message": finding.message})

    caps, manifest = load_capabilities(run_dir)
    schema = str(manifest.get("schema_version", ""))
    if schema_generation(schema) < int(contract.get("minimum_schema_generation", 11)):
        checks.append({"status": "FAIL", "code": "SCHEMA_TOO_OLD", "message": schema})

    package = str(fixture.get("package", ""))
    group = "catproduct" if package == "catproduct" else "catpart"
    accepted = contract.get("capability_acceptance", {}).get(group, {})
    for name, states in accepted.items():
        actual = str(caps.get(name, ""))
        if actual not in set(states):
            checks.append({"status": "FAIL", "code": "PHASE1_CAPABILITY_STATE", "message": f"{name}: {actual} not in {states}"})

    native_rows = load_jsonl(run_dir / "native_features.jsonl")
    for family in contract.get("payload_expectations", {}).get(fixture_id, []):
        if count_payload(native_rows, family) <= 0:
            checks.append({"status": "FAIL", "code": "PHASE1_PAYLOAD_MISSING", "message": f"{family} payload missing"})
    for family in contract.get("type_only_expected", {}).get(fixture_id, []):
        if count_type_only(native_rows, family) <= 0:
            checks.append({"status": "FAIL", "code": "PHASE1_TYPE_ONLY_MISSING", "message": f"{family} type-only row missing"})

    status = "PASS" if not checks else status_from([type("FindingLike", (), item) for item in checks])
    return {
        "fixture_id": fixture_id,
        "status": status,
        "source_commit": manifest.get("parser_git_commit", ""),
        "schema_version": schema,
        "capabilities": {name: caps.get(name, "") for name in sorted(set(accepted.keys()) | {"native_feature_topology_mapping"})},
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    catalog = load_json(args.catalog)
    contract = load_json(args.contract)
    fixture_ids = list(contract.get("required_fixtures", []))
    results = [evaluate_fixture(contract, catalog, args.results_dir, fixture_id) for fixture_id in fixture_ids]
    counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    report = {
        "contract_id": contract.get("contract_id"),
        "contract_version": contract.get("contract_version"),
        "results_dir": str(args.results_dir),
        "counts": counts,
        "fixtures": results,
        "status": "PASS" if counts.get("FAIL", 0) == 0 and counts.get("BLOCKED", 0) == 0 else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
