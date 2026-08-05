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

    def _semantic_validator(self, fixture=None, contract=None):
        base_contract = {
            "authoritative_feature_mapping": {
                "allowed_authority": ["catia_persistent_naming", "catia_selection_reference", "catia_history_result", "verified_r21_public_equivalent"],
                "require_forward_and_reverse": True,
            }
        }
        if contract:
            base_contract.update(contract)
        return RunValidator("completion", base_contract, fixture or {"id": "X", "native_expected": [], "roles": []}, Path("."))

    def _cap_metrics(self, **overrides):
        metrics = {
            "required_count": 1,
            "resolved_count": 0,
            "history_confirmed_count": 0,
            "authoritative_history_count": 0,
            "runtime_identity_count": 0,
            "candidate_count": 0,
            "ambiguous_count": 0,
            "unmatched_count": 0,
            "failed_count": 0,
            "coverage_ratio": 0.0,
            "runtime_coverage_ratio": 0.0,
            "authoritative_coverage_ratio": 0.0,
            "reason_code": "TEST",
        }
        metrics.update(overrides)
        return metrics

    def test_pointer_identity_cannot_claim_history_generated(self):
        validator = self._semantic_validator()
        validator.rows["native_feature_topology_links.jsonl"] = [{
            "mapping_method": "catia_resultout_final_cell_pointer_identity",
            "mapping_status": "confirmed",
            "authority": "catia_history_result",
            "relation_kind": "generated",
        }]
        validator.validate_feature_topology_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "POINTER_IDENTITY_NOT_AUTHORITATIVE" for item in validator.findings))

    def test_mapping_complete_with_unmatched_is_rejected(self):
        validator = self._semantic_validator()
        validator.rows["native_feature_topology_links.jsonl"] = [{"mapping_status": "unmatched", "mapping_direction": "result_cell_to_final_face"}]
        validator.json_docs["capabilities.json"] = {"native_feature_topology_mapping": "complete"}
        validator.validate_feature_topology_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "MAPPING_COMPLETE_HAS_NO_UNRESOLVED" for item in validator.findings))

    def test_capability_status_mismatch_is_rejected(self):
        validator = self._semantic_validator()
        metrics = {
            "required_count": 1, "resolved_count": 0, "history_confirmed_count": 0,
            "authoritative_history_count": 0,
            "runtime_identity_count": 1, "candidate_count": 0, "ambiguous_count": 0,
            "unmatched_count": 0, "failed_count": 0, "coverage_ratio": 0.0,
            "runtime_coverage_ratio": 1.0, "authoritative_coverage_ratio": 0.0,
            "reason_code": "RUNTIME_IDENTITY_ONLY",
        }
        validator.json_docs["capabilities.json"] = {"native_feature_topology_mapping": "partial", "capability_metrics": {"native_feature_topology_mapping": metrics}}
        validator.json_docs["capability_matrix.json"] = {"capabilities": [dict({"name": "native_feature_topology_mapping", "status": "complete", "evidence_count": 1}, **metrics)]}
        validator.validate_capability_consistency()
        self.assertTrue(any(item.status == "FAIL" and item.code == "CAPABILITY_STATUS_CONSISTENT" for item in validator.findings))

    def test_runtime_full_coverage_without_authority_cannot_complete(self):
        validator = self._semantic_validator()
        validator.rows["native_feature_topology_links.jsonl"] = [{
            "mapping_status": "runtime_matched",
            "mapping_direction": "result_cell_to_final_face",
            "authority": "runtime_cell_identity",
        }]
        metrics = self._cap_metrics(runtime_identity_count=1, runtime_coverage_ratio=1.0, authoritative_coverage_ratio=0.0, coverage_ratio=0.0)
        validator.json_docs["capabilities.json"] = {"native_feature_topology_mapping": "complete", "capability_metrics": {"native_feature_topology_mapping": metrics}}
        validator.validate_feature_topology_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "RUNTIME_COVERAGE_CANNOT_COMPLETE_MAPPING" for item in validator.findings))

    def test_authority_coverage_without_reverse_cannot_complete(self):
        validator = self._semantic_validator()
        validator.rows["native_feature_topology_links.jsonl"] = [{
            "mapping_status": "confirmed",
            "authority": "verified_r21_public_equivalent",
            "persistent_reference": "GN://face/1",
            "mapping_direction": "result_cell_to_final_face",
        }]
        metrics = self._cap_metrics(resolved_count=1, history_confirmed_count=1, authoritative_history_count=1, runtime_coverage_ratio=1.0, authoritative_coverage_ratio=1.0, coverage_ratio=1.0)
        validator.json_docs["capabilities.json"] = {"native_feature_topology_mapping": "complete", "capability_metrics": {"native_feature_topology_mapping": metrics}}
        validator.validate_feature_topology_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "MAPPING_FORWARD_REVERSE" for item in validator.findings))

    def test_zero_required_mapping_cannot_complete(self):
        validator = self._semantic_validator()
        metrics = self._cap_metrics(required_count=0, resolved_count=0, coverage_ratio=0.0, runtime_coverage_ratio=0.0, authoritative_coverage_ratio=0.0)
        validator.json_docs["capabilities.json"] = {"native_feature_topology_mapping": "complete", "capability_metrics": {"native_feature_topology_mapping": metrics}}
        validator.json_docs["capability_matrix.json"] = {"capabilities": [dict({"name": "native_feature_topology_mapping", "status": "complete", "evidence_count": 0}, **metrics)]}
        validator.validate_feature_topology_semantics()
        validator.validate_capability_consistency()
        self.assertTrue(any(item.status == "FAIL" and item.code == "MAPPING_COMPLETE_REQUIRES_AUTHORITATIVE_COVERAGE" for item in validator.findings))

    def test_capability_metric_mismatch_is_rejected(self):
        validator = self._semantic_validator()
        caps_metrics = self._cap_metrics(runtime_coverage_ratio=1.0)
        matrix_metrics = self._cap_metrics(runtime_coverage_ratio=0.5)
        validator.json_docs["capabilities.json"] = {"native_feature_topology_mapping": "partial", "capability_metrics": {"native_feature_topology_mapping": caps_metrics}}
        validator.json_docs["capability_matrix.json"] = {"capabilities": [dict({"name": "native_feature_topology_mapping", "status": "partial", "evidence_count": 1}, **matrix_metrics)]}
        validator.validate_capability_consistency()
        self.assertTrue(any(item.status == "FAIL" and item.code == "CAPABILITY_METRICS_CONSISTENT" for item in validator.findings))

    def test_persistent_authority_requires_reference(self):
        validator = self._semantic_validator()
        validator.rows["native_feature_topology_links.jsonl"] = [{
            "mapping_status": "confirmed",
            "authority": "catia_selection_reference",
            "persistent_reference": "",
        }]
        validator.validate_feature_topology_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "PERSISTENT_REFERENCE_REQUIRED" for item in validator.findings))

    def test_complete_mapping_requires_reverse_direction(self):
        validator = self._semantic_validator()
        validator.rows["native_feature_topology_links.jsonl"] = [{
            "mapping_status": "confirmed",
            "authority": "verified_r21_public_equivalent",
            "persistent_reference": "GN://face/1",
            "mapping_direction": "result_cell_to_final_face",
        }]
        validator.json_docs["capabilities.json"] = {"native_feature_topology_mapping": "complete"}
        validator.validate_feature_topology_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "MAPPING_FORWARD_REVERSE" for item in validator.findings))

    def test_multi_generated_requires_authoritative_history(self):
        validator = self._semantic_validator()
        validator.rows["native_feature_topology_links.jsonl"] = [
            {"final_cell_id": "FACE1", "source_feature_id": "F1", "relation_kind": "generated", "authority": "runtime_cell_identity"},
            {"final_cell_id": "FACE1", "source_feature_id": "F2", "relation_kind": "generated", "authority": "runtime_cell_identity"},
        ]
        validator.validate_feature_topology_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "MULTI_GENERATED_REQUIRES_HISTORY" for item in validator.findings))

    def test_startup_type_only_cannot_claim_decoded_payload(self):
        validator = self._semantic_validator()
        validator.rows["native_features.jsonl"] = [{
            "decoder": "StartupTypeCanonicalDecoder",
            "decoder_status": "decoded",
            "payload_extraction_status": "not_implemented",
        }]
        validator.validate_decoder_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "STARTUP_TYPE_IS_TYPE_ONLY" for item in validator.findings))

    def test_parameter_complete_requires_every_payload_decoded(self):
        validator = self._semantic_validator()
        validator.rows["native_features.jsonl"] = [
            {
                "decoder": "NativeHoleDecoder",
                "decoder_status": "decoded",
                "payload_extraction_status": "complete",
                "payload_type": "native_hole",
            },
            {
                "decoder": "StartupTypeCanonicalDecoder",
                "decoder_status": "type_only",
                "payload_extraction_status": "not_implemented",
                "payload_type": "",
            },
        ]
        validator.json_docs["capabilities.json"] = {"native_feature_parameter_extraction": "complete"}
        validator.validate_decoder_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "FEATURE_PARAMETER_COMPLETE_REQUIRES_PAYLOADS" for item in validator.findings))

    def test_brep_topology_complete_requires_coedges_and_loops(self):
        validator = self._semantic_validator()
        validator.rows["native_topology_cells.jsonl"] = [
            {"cell_id": "F1", "dimension": 2, "boundary_cell_ids": ["E1"], "adjacent_cell_ids": []},
            {"cell_id": "E1", "dimension": 1, "boundary_cell_ids": [], "adjacent_cell_ids": ["F1"]},
        ]
        validator.rows["native_topology_wires.jsonl"] = []
        validator.json_docs["capabilities.json"] = {
            "final_brep_topology_extraction": "complete",
            "capability_metrics": {"final_brep_topology_extraction": {"coedge_count": 0}},
        }
        validator.validate_brep_capability_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "BREP_COMPLETE_FACE_HAS_LOOP" for item in validator.findings))
        self.assertTrue(any(item.status == "FAIL" and item.code == "BREP_COMPLETE_REQUIRES_COEDGES" for item in validator.findings))

    def test_brep_geometry_complete_requires_exact_parameters(self):
        validator = self._semantic_validator()
        validator.rows["native_topology_cells.jsonl"] = [
            {"cell_id": "F1", "dimension": 2, "geometry_type": "success", "geometry_parameters": {}},
        ]
        validator.json_docs["capabilities.json"] = {"final_brep_geometry_extraction": "complete"}
        validator.validate_brep_capability_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "BREP_GEOMETRY_COMPLETE_REQUIRES_PARAMETERS" for item in validator.findings))
        self.assertTrue(any(item.status == "FAIL" and item.code == "BREP_GEOMETRY_COMPLETE_REQUIRES_TYPES" for item in validator.findings))

    def test_mesh_mapping_complete_requires_all_faces(self):
        validator = self._semantic_validator()
        validator.rows["native_topology_cells.jsonl"] = [
            {"cell_id": "F1", "dimension": 2},
            {"cell_id": "F2", "dimension": 2},
        ]
        validator.rows["native_mesh_face_map.jsonl"] = [
            {"mesh_map_id": "M1", "face_cell_id": "F1", "triangle_count": 2, "tessellation_status": "success"},
        ]
        validator.json_docs["capabilities.json"] = {"mesh_brep_face_mapping": "complete"}
        validator.validate_mesh_mapping_capability_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "MESH_COMPLETE_ALL_FACES_MAPPED" for item in validator.findings))

    def test_product_transform_numeric_truth_rejects_wrong_matrix(self):
        validator = self._semantic_validator(fixture={"id": "PRODUCT-01", "native_expected": []})
        validator.rows["product_instances.jsonl"] = [
            {
                "instance_path": "CAA_PRODUCT_MULTI_INSTANCE/PadReference_Instance_A",
                "transform_4x4": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            },
            {
                "instance_path": "CAA_PRODUCT_MULTI_INSTANCE/PadReference_Instance_B",
                "transform_4x4": [1, 0, 0, 140, 0, 1, 0, 20, 0, 0, 1, 0, 0, 0, 0, 1],
            },
        ]
        validator.validate_product_numeric_truth()
        self.assertTrue(any(item.status == "FAIL" and item.code == "PRODUCT_TRANSFORM_EXPECTED_MATRIX" for item in validator.findings))

    def _product_validator(self, rows, caps):
        validator = self._semantic_validator(fixture={"id": "PRODUCT-X", "native_expected": [], "package": "catproduct"})
        validator.rows["product_instances.jsonl"] = rows
        validator.json_docs["capabilities.json"] = caps
        return validator

    def _root_row(self):
        return {
            "instance_id": "root",
            "parent_instance_id": "",
            "reference_id": "ref-root",
            "instance_path": "ROOT",
            "depth": 0,
            "transform_status": "identity_root",
            "transform_4x4": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        }

    def _child_row(self, instance_id="child1", path="ROOT/Child1", matrix=None, status="resolved_absolute"):
        if matrix is None:
            matrix = [1, 0, 0, 10, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        return {
            "instance_id": instance_id,
            "parent_instance_id": "root",
            "reference_id": f"ref-{instance_id}",
            "instance_path": path,
            "depth": 1,
            "transform_status": status,
            "transform_4x4": matrix,
        }

    def test_root_only_product_transform_is_not_applicable(self):
        validator = self._product_validator(
            [self._root_row()],
            {"product_structure_extraction": "complete", "instance_transform_extraction": "not_applicable"},
        )
        validator.validate_product_capability_semantics()
        self.assertFalse(any(item.status == "FAIL" for item in validator.findings))

    def test_product_complete_rejects_missing_instance_matrix(self):
        bad = self._child_row("child2", "ROOT/Child2", matrix=[])
        validator = self._product_validator(
            [self._root_row(), self._child_row(), bad],
            {"product_structure_extraction": "complete", "instance_transform_extraction": "complete"},
        )
        validator.validate_product_capability_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "PRODUCT_TRANSFORM_COMPLETE_ALL_INSTANCES" for item in validator.findings))

    def test_product_complete_rejects_duplicate_instance_paths(self):
        validator = self._product_validator(
            [self._root_row(), self._child_row("child1", "ROOT/Dup"), self._child_row("child2", "ROOT/Dup")],
            {"product_structure_extraction": "complete", "instance_transform_extraction": "complete"},
        )
        validator.validate_product_capability_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "PRODUCT_INSTANCE_PATH_UNIQUE" for item in validator.findings))

    def test_product_complete_rejects_bad_rotation(self):
        bad_rotation = [2, 0, 0, 10, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        validator = self._product_validator(
            [self._root_row(), self._child_row(matrix=bad_rotation)],
            {"product_structure_extraction": "complete", "instance_transform_extraction": "complete"},
        )
        validator.validate_product_capability_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "PRODUCT_TRANSFORM_COMPLETE_ALL_INSTANCES" for item in validator.findings))

    def test_product_complete_rejects_relative_transform_status(self):
        validator = self._product_validator(
            [self._root_row(), self._child_row(status="resolved_relative")],
            {"product_structure_extraction": "complete", "instance_transform_extraction": "complete"},
        )
        validator.validate_product_capability_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "PRODUCT_TRANSFORM_COMPLETE_ALL_INSTANCES" for item in validator.findings))

    def test_catpart_cannot_claim_product_capability_complete(self):
        validator = self._semantic_validator(fixture={"id": "PD-PAD-01", "native_expected": [], "package": "part_design"})
        validator.json_docs["capabilities.json"] = {"product_structure_extraction": "complete", "instance_transform_extraction": "complete"}
        validator.rows["product_instances.jsonl"] = [self._root_row()]
        validator.validate_product_capability_semantics()
        self.assertTrue(any(item.status == "FAIL" and item.code == "CATPART_PRODUCT_CAPABILITY_NOT_APPLICABLE" for item in validator.findings))


if __name__ == "__main__":
    unittest.main()
