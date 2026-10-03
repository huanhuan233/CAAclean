"""Validate the P0 traceability manifests without importing application dependencies."""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "development"
REQUIRED_REQUIREMENT_FIELDS = {
    "requirement_id", "source_id", "source_locator", "source_status",
    "original_summary", "module", "classification", "required_inputs",
    "expected_outputs", "identity_and_coordinates", "current_implementation",
    "verification_status", "phase", "fixtures", "gap",
}
REQUIRED_FIXTURE_FIELDS = {
    "fixture_id", "path", "origin", "restriction", "input_type", "provenance",
    "units", "coordinates", "instances", "known_features", "expected_value",
    "expected_value_source", "requirements", "availability", "sha256",
}


def validate() -> list[str]:
    requirements = json.loads((DOCS / "requirements.json").read_text(encoding="utf-8"))
    fixtures = json.loads((DOCS / "fixtures.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    sources = {item["source_id"] for item in requirements["sources"]}
    rows = requirements["requirements"]
    fixture_rows = fixtures["fixtures"]
    requirement_ids = {item.get("requirement_id") for item in rows}
    fixture_ids = {item.get("fixture_id") for item in fixture_rows}
    if len(requirement_ids) != len(rows):
        errors.append("duplicate requirement_id")
    if len(fixture_ids) != len(fixture_rows):
        errors.append("duplicate fixture_id")
    for expected in (f"F{number:02d}" for number in range(1, 11)):
        if expected not in requirement_ids:
            errors.append(f"missing {expected}")
    for item in rows:
        rid = item.get("requirement_id", "<missing>")
        for field in REQUIRED_REQUIREMENT_FIELDS - item.keys():
            errors.append(f"{rid}: missing {field}")
        if item.get("source_id") not in sources:
            errors.append(f"{rid}: unknown source")
        if item.get("module") not in {f"F{number:02d}" for number in range(1, 11)}:
            errors.append(f"{rid}: invalid module")
        if not item.get("original_summary") or not item.get("required_inputs") or not item.get("expected_outputs"):
            errors.append(f"{rid}: empty requirement content")
        for fixture_id in item.get("fixtures", []):
            if fixture_id not in fixture_ids:
                errors.append(f"{rid}: unknown fixture {fixture_id}")
    for item in fixture_rows:
        fid = item.get("fixture_id", "<missing>")
        for field in REQUIRED_FIXTURE_FIELDS - item.keys():
            errors.append(f"{fid}: missing {field}")
        if item.get("path"):
            path = ROOT / item["path"]
            if not path.is_file():
                errors.append(f"{fid}: missing file")
            elif not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256") or ""):
                errors.append(f"{fid}: invalid sha256")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                errors.append(f"{fid}: sha256 mismatch")
        for rid in item.get("requirements", []):
            if rid not in requirement_ids:
                errors.append(f"{fid}: unknown requirement {rid}")
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        raise SystemExit("\n".join(problems))
    print("P0 manifests valid")
