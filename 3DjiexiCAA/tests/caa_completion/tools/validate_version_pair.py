#!/usr/bin/env python3
"""Validate that a V1/V2 fixture pair is genuinely distinct and exposes changed CAA evidence."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-id", required=True)
    parser.add_argument("--run-v1", type=Path, required=True)
    parser.add_argument("--run-v2", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    findings = []
    manifest1 = json.loads((args.run_v1 / "manifest.json").read_text(encoding="utf-8-sig"))
    manifest2 = json.loads((args.run_v2 / "manifest.json").read_text(encoding="utf-8-sig"))
    input1 = manifest1.get("input", {}).get("sha256")
    input2 = manifest2.get("input", {}).get("sha256")
    distinct_input = bool(input1 and input2 and input1 != input2)
    findings.append({"status": "PASS" if distinct_input else "FAIL", "code": "PAIR_INPUT_DISTINCT", "message": "V1/V2 input SHA differs" if distinct_input else "V1/V2 input SHA is missing or identical"})
    candidates = [
        "native_features.jsonl", "native_feature_topology_links.jsonl", "native_topology_cells.jsonl",
        "fta_semantics.jsonl", "fta_topology_links.jsonl", "product_instances.jsonl",
        "parameters.jsonl", "business_features.jsonl",
    ]
    differences = []
    for name in candidates:
        p1, p2 = args.run_v1 / name, args.run_v2 / name
        if p1.is_file() and p2.is_file() and digest(p1) != digest(p2):
            differences.append(name)
    changed = bool(differences)
    findings.append({"status": "PASS" if changed else "FAIL", "code": "PAIR_CAA_EVIDENCE_CHANGED", "message": f"changed artifacts: {differences}" if changed else "no relevant CAA evidence changed between V1 and V2"})
    status = "PASS" if all(item["status"] == "PASS" for item in findings) else "FAIL"
    report = {"fixture_id": args.fixture_id, "mode": "version_pair", "status": status, "findings": findings}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[{status}] {args.fixture_id} differences={differences}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

