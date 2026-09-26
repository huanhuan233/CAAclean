"""Compare the same part/product before and after semantic-reader changes."""
import json
import sys
import unittest
from pathlib import Path

BASELINE, CURRENT = (Path(sys.argv.pop(1)) for _ in range(2))


def records(bundle, name):
    with (bundle / name).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


class SemanticCompatibilityTests(unittest.TestCase):
    def test_object_identity_and_labels_are_preserved(self):
        fields = ('object_id', 'document_id', 'display_name', 'internal_name', 'startup_type')
        before = {tuple(o.get(k) for k in fields) for o in records(BASELINE, 'object_entities.jsonl')}
        after = {tuple(o.get(k) for k in fields) for o in records(CURRENT, 'object_entities.jsonl')}
        self.assertEqual(before, after)

    def test_occurrence_hierarchy_and_paths_are_preserved(self):
        fields = ('occurrence_id', 'object_id', 'parent_occurrence_id', 'tree_path', 'occurrence_kind')
        before = {tuple(o.get(k) for k in fields) for o in records(BASELINE, 'tree_occurrences.jsonl')}
        after = {tuple(o.get(k) for k in fields) for o in records(CURRENT, 'tree_occurrences.jsonl')}
        self.assertEqual(before, after)

    def test_existing_parameter_values_are_preserved(self):
        def values(bundle):
            return {(f['subject_id'], f['key']): f['raw_value']
                    for f in records(bundle, 'property_facts.jsonl')
                    if f['key'] == 'catia_parameter_value_text' and f['read_status'] == 'available'}
        before, after = values(BASELINE), values(CURRENT)
        self.assertTrue(before, 'baseline must exercise existing parameter values')
        for key, value in before.items():
            self.assertEqual(after.get(key), value, key)

    def test_assembly_instances_and_transforms_are_preserved(self):
        self.assertEqual(records(BASELINE, 'product_occurrences.jsonl'),
                         records(CURRENT, 'product_occurrences.jsonl'))


if __name__ == '__main__':
    unittest.main()
