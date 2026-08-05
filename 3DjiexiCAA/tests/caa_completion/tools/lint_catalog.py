#!/usr/bin/env python3
"""Static checks for the fixture catalog."""

import argparse
import json
from pathlib import Path


REQUIRED_PACKAGES = {
    "native_part_design", "gsd_native", "manufacturing_geometry_evidence",
    "topology_mapping_pressure", "boundary_negative", "fta_mbd",
    "properties_measurement", "business_connections", "catproduct",
    "version_pairs", "feature_registry",
}
VALID_CREATION = {"reuse", "auto", "auto_probe", "manual_required", "derived_pair", "self_test"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()
    data = json.loads(args.catalog.read_text(encoding="utf-8-sig"))
    fixtures = data.get("fixtures", [])
    errors = []
    ids = set()
    packages = set()
    for index, item in enumerate(fixtures, 1):
        fixture_id = item.get("id")
        if not fixture_id or fixture_id in ids:
            errors.append(f"row {index}: missing/duplicate id {fixture_id!r}")
        ids.add(fixture_id)
        packages.add(item.get("package"))
        if item.get("creation") not in VALID_CREATION:
            errors.append(f"{fixture_id}: invalid creation {item.get('creation')!r}")
        if not item.get("file"):
            errors.append(f"{fixture_id}: missing file")
        if not isinstance(item.get("variants"), list) or not item.get("variants"):
            errors.append(f"{fixture_id}: variants must be non-empty")
        if item.get("completion_required") is not True:
            errors.append(f"{fixture_id}: completion_required must remain true")
    missing_packages = REQUIRED_PACKAGES - packages
    if missing_packages:
        errors.append(f"missing packages: {sorted(missing_packages)}")
    if errors:
        for error in errors:
            print("[FAIL]", error)
        return 1
    print(f"[PASS] catalog fixtures={len(fixtures)} packages={len(packages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

