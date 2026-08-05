import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from validate_caa_outputs import RunValidator, compare_runs, load_jsonl, schema_generation  # noqa: E402


class ValidatorTests(unittest.TestCase):
    def test_schema_generation(self):
        self.assertEqual(schema_generation("cad_parse_mvp_v9"), 9)
        self.assertEqual(schema_generation("cad_parse_mvp_v10"), 10)
        self.assertEqual(schema_generation("unknown"), -1)

    def test_invalid_jsonl_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.jsonl"
            path.write_text("[]\n", encoding="utf-8")
            with self.assertRaises(Exception):
                load_jsonl(path)

    def test_coverage_conservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "features.jsonl").write_text(
                json.dumps({"feature_id": "F1", "parent_id": ""}) + "\n", encoding="utf-8"
            )
            (root / "coverage.json").write_text(
                json.dumps({"enumerated_total": 1, "typed_count": 1, "generic_count": 0, "opaque_count": 0, "failed_count": 0}),
                encoding="utf-8",
            )
            contract = {
                "required_artifacts": ["features.jsonl", "coverage.json"],
                "jsonl_required_fields": {"features.jsonl": ["feature_id", "parent_id"]},
                "source": {"schema_version": "cad_parse_mvp_v9"},
            }
            validator = RunValidator("baseline", contract, {"id": "X", "native_expected": []}, root)
            findings = validator.run()
            self.assertFalse(any(item.status == "FAIL" and item.code == "COVERAGE_CONSERVED" for item in findings))

    def test_completion_rejects_candidate_only_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = {"mapping_status": "candidate", "mapping_method": "geometry_fingerprint"}
            (root / "native_feature_topology_links.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            contract = {
                "required_artifacts": ["native_feature_topology_links.jsonl"],
                "target_jsonl_fields": {"native_feature_topology_links.jsonl": ["mapping_status", "mapping_method"]},
                "authoritative_feature_mapping": {"required_status": "confirmed", "allowed_authority": [], "forbidden_as_authority": ["geometry_fingerprint"]},
            }
            validator = RunValidator("completion", contract, {"id": "X", "native_expected": [], "roles": []}, root)
            findings = validator.run()
            self.assertTrue(any(item.status == "FAIL" and item.code == "AUTHORITATIVE_MAPPING_PRESENT" for item in findings))

    def test_determinism_detects_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / "a", root / "b"
            a.mkdir(); b.mkdir()
            (a / "features.jsonl").write_text("{}\n", encoding="utf-8")
            (b / "features.jsonl").write_text('{"x":1}\n', encoding="utf-8")
            findings = compare_runs(a, b, ["features.jsonl"])
            self.assertEqual(findings[0].status, "FAIL")


if __name__ == "__main__":
    unittest.main()

