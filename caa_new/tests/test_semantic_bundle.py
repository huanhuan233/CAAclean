"""Acceptance tests for the supplied composite CATPart; never changes its bundle."""
import json
import sys
import unittest
from pathlib import Path

BUNDLE = Path(sys.argv.pop(1))


class SemanticBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (BUNDLE / 'property_facts.jsonl').open(encoding='utf-8') as stream:
            cls.facts = [json.loads(line) for line in stream]
        with (BUNDLE / 'object_entities.jsonl').open(encoding='utf-8') as stream:
            cls.objects = [json.loads(line) for line in stream]

    def values(self, key):
        return [f for f in self.facts if f['key'] == key and f['read_status'] == 'available']

    def test_numeric_parameters_are_not_silently_skipped(self):
        self.assertTrue([f for f in self.values('catia_parameter_value_text') if f['value_type'] == 'number'])

    def test_material_thickness_is_si_not_display_millimetres(self):
        facts = self.values('composite_cured_thickness')
        self.assertTrue(facts, 'missing typed material thickness')
        self.assertAlmostEqual(float(facts[0]['raw_value']), 0.00033, places=9)
        self.assertEqual(facts[0]['raw_unit'], 'm')

    def test_composite_density_is_not_inertia_default(self):
        facts = self.values('composite_density')
        self.assertTrue(facts, 'missing composite material density')
        self.assertAlmostEqual(float(facts[0]['raw_value']), 1500)

    def test_each_ply_has_typed_orientation(self):
        plies = {o['object_id'] for o in self.objects if o['startup_type'] == 'CATCompPly'}
        self.assertEqual(len(plies), 4)
        facts = [f for f in self.values('composite_orientation') if f['subject_id'] in plies]
        self.assertEqual({f['subject_id'] for f in facts}, plies)

    def test_existing_tree_is_preserved(self):
        self.assertEqual(len(self.objects), 16706)
        with (BUNDLE / 'tree_occurrences.jsonl').open(encoding='utf-8') as stream:
            self.assertEqual(sum(1 for _ in stream), 34191)

    def test_composite_properties_have_one_result_per_subject_and_key(self):
        seen = set()
        for fact in self.facts:
            if not fact['key'].startswith('composite_'):
                continue
            identity = fact['subject_id'], fact['key']
            self.assertNotIn(identity, seen, 'do not mix failed direct probes with successful referenced material values')
            seen.add(identity)

    def test_material_cost_and_direction_palette_are_captured(self):
        cost = self.values('composite_cost_per_mass')
        self.assertTrue(cost)
        self.assertAlmostEqual(float(cost[0]['raw_value']), 23.8)
        for index in range(1, 5):
            self.assertTrue(self.values(f'composite_direction_{index}'))
            self.assertTrue(self.values(f'composite_direction_{index}_rgb'))

    def test_ply_contour_vertices_are_native_geometry_not_xml_constants(self):
        plies = {o['object_id'] for o in self.objects if o['startup_type'] == 'CATCompPly'}
        vertices = [f for f in self.values('composite_contour_vertices_mm') if f['subject_id'] in plies]
        self.assertEqual({f['subject_id'] for f in vertices}, plies)
        for fact in vertices:
            points = json.loads(fact['raw_value'])
            self.assertEqual(len(points), 4)
            self.assertEqual({tuple(round(v, 8) for v in p) for p in points}, {(500,500,0), (500,-500,0), (-500,500,0), (-500,-500,0)})

    def test_each_ply_has_native_area_and_center(self):
        plies = {o['object_id'] for o in self.objects if o['startup_type'] == 'CATCompPly'}
        areas = self.values('composite_area_m2')
        self.assertEqual(len(areas), 4)
        self.assertEqual({f['subject_id'] for f in areas}, plies)
        for fact in areas:
            self.assertAlmostEqual(float(fact['raw_value']), 1.0)
        for coordinate in ('x', 'y', 'z'):
            centers = self.values(f'composite_center_{coordinate}_m')
            self.assertEqual({f['subject_id'] for f in centers}, plies)
            for fact in centers:
                self.assertEqual(fact['raw_unit'], 'm')
                self.assertAlmostEqual(float(fact['raw_value']), 0.0, places=9)

    def test_composite_native_attributes_are_preserved_without_name_guessing(self):
        self.assertTrue([f for f in self.facts if f['key'].startswith('native_attribute:') and f['read_status'] == 'available'])


if __name__ == '__main__':
    unittest.main()
