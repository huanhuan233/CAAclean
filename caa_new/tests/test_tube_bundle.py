"""导管实件验收：python test_tube_bundle.py <capture-directory>。"""
import json
import math
import sys
import unittest
from pathlib import Path

BUNDLE = Path(sys.argv.pop(1))


def records(name):
    """读取原始采集记录，不通过界面缓存判断结果。"""
    with (BUNDLE / name).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


class TubeBundleTests(unittest.TestCase):
    def setUp(self):
        """为每项验收建立事实和对象索引。"""
        self.facts = records("property_facts.jsonl")
        self.objects = {x["object_id"] for x in records("object_entities.jsonl")}

    def test_ordered_measured_centerline(self):
        """验证七直六弯、实测长度和几何派生属性的来源声明。"""
        paths = [p for p in self.facts if p["key"] == "tube_bending_geometry"]
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0]["authority"], "derived_geometry")
        path = json.loads(paths[0]["raw_value"])
        segments = path["segments"]
        self.assertEqual([s["kind"] for s in segments], ["line", "arc"] * 6 + ["line"])
        self.assertAlmostEqual(path["developed_length_mm"], 1091.4902918769662, places=5)
        self.assertAlmostEqual(sum(s["length_mm"] for s in segments), path["developed_length_mm"])
        bends = [s for s in segments if s["kind"] == "arc"]
        self.assertIsNone(bends[0]["rotation_deg"])
        for i, bend in enumerate(bends):
            self.assertAlmostEqual(bend["radius_mm"], 18, places=7)
            self.assertAlmostEqual(math.radians(bend["bend_deg"]) * 18, bend["length_mm"], places=5)
            self.assertAlmostEqual(bend["straight_before_mm"], segments[2*i]["length_mm"])
        self.assertEqual(path["machine_compensation_status"], "not_provided")
        self.assertEqual(path["sequence_kind"], "geometric_traversal_not_machine_operations")
        for left, right in zip(segments, segments[1:]):
            self.assertLess(math.dist(left["end_mm"], right["start_mm"]), .001)
        self.assertTrue(all(s["source_id"] in self.objects for s in segments))
        projected = [f for f in records("native_features.jsonl") if "native_sweep_path" in f]
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["native_sweep_path"], path)

    def test_formula_bodies_and_reference_integrity(self):
        """五条公式有正文、输入输出，并且依赖没有悬空对象。"""
        formulas = [p for p in self.facts if p["key"] == "formula_expression"]
        self.assertEqual(len(formulas), 5)
        for formula in formulas:
            self.assertTrue(formula["raw_value"])
            keys = {p["key"] for p in self.facts if p["subject_id"] == formula["subject_id"]}
            self.assertIn("formula_output_1", keys)
            self.assertIn("formula_input_1", keys)
            for fact in self.facts:
                if fact["subject_id"] != formula["subject_id"]:
                    continue
                if not fact["key"].startswith(("formula_input_", "formula_output_")) or not fact["key"].rsplit("_", 1)[-1].isdigit():
                    continue
                if fact["read_status"] == "non_spec_parameter":
                    # 对象值参数本身不在树上，但实际指向的规格对象必须能够追溯。
                    related = {f["key"]: f for f in self.facts if f["subject_id"] == formula["subject_id"]}
                    self.assertEqual(related[fact["key"] + "_value_text"]["read_status"], "available")
                    fact = related[fact["key"] + "_value_object"]
                self.assertEqual(fact["read_status"], "available")
                self.assertIn(fact["raw_value"], self.objects)
                self.assertTrue(any(d["from_feature_id"] == formula["subject_id"]
                                    and d["to_feature_id"] == fact["raw_value"]
                                    and d["dependency_kind"] == fact["key"]
                                    for d in records("feature_dependencies.jsonl")))
        targets = self.objects | {t["topology_id"] for t in records("topology_entities.jsonl")}
        for dep in records("feature_dependencies.jsonl"):
            self.assertIn(dep["from_feature_id"], self.objects)
            self.assertIn(dep["to_feature_id"], targets)

    def test_existing_process_notes_survive(self):
        """原有规范文字仍是原始事实，不由新计算模块替代。"""
        text = "\n".join(p["raw_value"] for p in self.facts)
        self.assertIn("PS D1200", text)
        self.assertIn("GF D2900K114C1", text)
        self.assertIn("Ti-3Al-2.5V", text)


if __name__ == "__main__":
    unittest.main()
