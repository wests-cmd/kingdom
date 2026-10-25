"""Real trained artifacts; no model server or inference dependencies required."""
import math
import unittest
from backend.models.decision_selectors import rank, recommend_models, recommend_knights, status, shadow_models


class DecisionSelectorsTest(unittest.TestCase):
    def test_dynamic_inventory_and_type_preferences(self):
        cloud = {'id': 'new-cloud', 'hosting': 'cloud', 'decision_task_types': ['coding']}
        local = {'id': 'new-local', 'hosting': 'local', 'decision_task_types': ['coding']}
        self.assertEqual(recommend_models([cloud, local], ['coding'])[0], 'new-local')
        self.assertEqual(recommend_models([cloud], ['coding']), ['new-cloud'])
        self.assertEqual(recommend_models([]), [])
        self.assertEqual(shadow_models([local])['affects_execution'], False)

    def test_count_cannot_create_capacity_or_tasks(self):
        nodes = [{'id': 'light', 'fit': 0, 'load': .7},
                 {'id': 'worker', 'fit': 1, 'idle': 1, 'memory_headroom': .8}]
        result = recommend_knights(nodes, independent_tasks=6, owner_parallel_limit=1)
        self.assertEqual(result['knights'], ['worker'])
        self.assertEqual(recommend_knights(nodes, independent_tasks=0, owner_parallel_limit=4)['count'], 0)
        self.assertEqual(recommend_knights([], independent_tasks=5, owner_parallel_limit=4)['count'], 0)
        self.assertEqual(recommend_knights(nodes, independent_tasks=5, owner_parallel_limit=4)['count'], 2)

    def test_invalid_features_and_limits_fail_closed(self):
        for value in (math.nan, math.inf, 'fast', None):
            with self.assertRaises(ValueError):
                rank('model', [{'id': 'x', 'fit': value}])
        for value in (-1, 257, True, 1.5):
            with self.assertRaises(ValueError):
                recommend_knights([], independent_tasks=value, owner_parallel_limit=1)
        with self.assertRaises(ValueError):
            rank('knight', [{'id': 'same'}, {'id': 'same'}])

    def test_evidence_is_explicit_and_hashes_match(self):
        report = status()
        self.assertTrue(report['artifact_hashes_verified'])
        self.assertFalse(report['production_autonomy_proven'])
        for item in report['training']['models'].values():
            self.assertEqual(item['labels'], 'synthetic resource policy')
            self.assertGreater(item['multi_fact_policy_accuracy'], .85)


if __name__ == '__main__':
    unittest.main()
