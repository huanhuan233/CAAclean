#!/usr/bin/env python3
"""Create suite_summary.json and a readable Markdown capability report."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-known-blocked-fixtures", action="store_true")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8-sig"))
    fixture_by_id = {f["id"]: f for f in catalog["fixtures"]}
    reports = []
    for path in sorted(args.reports.glob("*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if "fixture_id" in report and "status" in report:
            reports.append(report)
    counts = Counter(report["status"] for report in reports)
    by_package = defaultdict(Counter)
    for report in reports:
        package = fixture_by_id.get(report["fixture_id"], {}).get("package", "unknown")
        by_package[package][report["status"]] += 1
    expected = {f["id"] for f in catalog["fixtures"]}
    observed = {r["fixture_id"] for r in reports}
    missing = sorted(expected - observed)
    unexpected_blocked = counts.get("BLOCKED", 0)
    known_limited = counts.get("BLOCKED_FIXTURE_R21", 0) + counts.get("UNTESTED_NO_FIXTURE", 0)
    if counts.get("FAIL", 0) == 0 and unexpected_blocked == 0 and not missing:
        overall = "PASS_WITH_KNOWN_LIMITS" if args.allow_known_blocked_fixtures and known_limited else "PASS"
    else:
        overall = "FAIL"
    summary = {
        "overall_status": overall,
        "report_count": len(reports),
        "expected_fixture_count": len(expected),
        "counts": dict(counts),
        "missing_reports": missing,
        "packages": {key: dict(value) for key, value in sorted(by_package.items())},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "suite_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# CAA completion suite report", "", f"Overall: **{overall}**", "", "| Package | PASS | FAIL | BLOCKED | BLOCKED_FIXTURE_R21 | UNTESTED_NO_FIXTURE |", "|---|---:|---:|---:|---:|---:|"]
    for package, values in sorted(by_package.items()):
        lines.append(f"| {package} | {values.get('PASS',0)} | {values.get('FAIL',0)} | {values.get('BLOCKED',0)} | {values.get('BLOCKED_FIXTURE_R21',0)} | {values.get('UNTESTED_NO_FIXTURE',0)} |")
    if missing:
        lines.extend(["", "## Missing fixture reports", ""] + [f"- {item}" for item in missing])
    failed = [r for r in reports if r["status"] != "PASS"]
    if failed:
        lines.extend(["", "## Non-passing fixtures", ""])
        for report in failed:
            first = next((f for f in report.get("findings", []) if f.get("status") == "FAIL"), {})
            lines.append(f"- `{report['fixture_id']}` — {report['status']}: {first.get('code','')} {first.get('message','')}")
    (args.output / "suite_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[{overall}] reports={len(reports)} missing={len(missing)} counts={dict(counts)}")
    return 0 if overall in {"PASS", "PASS_WITH_KNOWN_LIMITS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
