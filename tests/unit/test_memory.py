import unittest
from backend.memory.persistence import MemoryStore

import tempfile
from backend.memory.service import MemoryService

class TestMemoryStore(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()

    def test_memory_add_and_search(self):
        rec = self.store.add_memory("Unique secret codebase architecture note", metadata={"category": "audit"})
        self.assertIsNotNone(rec["id"])

        results = self.store.search_memory("codebase architecture")
        self.assertTrue(len(results) >= 1)
        self.assertIn("Unique secret codebase", results[0]["content"])

class TestMemoryServiceCachedSearch(unittest.TestCase):

    def test_memory_service_search_uses_word_cache(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = MemoryService(data_dir=tmp_dir)
            entry1 = service.add("Analysis of autonomous swarm intelligence and task routing")
            entry2 = service.add("Security audit of zero trust prompt firewall rules")

            # First search populates word cache
            res1 = service.search("swarm intelligence", limit=5)
            self.assertEqual(len(res1), 1)
            self.assertEqual(res1[0]["id"], entry1["id"])
            self.assertIn(entry1["id"], service._word_cache)
            self.assertIn(entry2["id"], service._word_cache)

            # Second search uses cached word sets
            res2 = service.search("zero trust security", limit=5)
            self.assertEqual(len(res2), 1)
            self.assertEqual(res2[0]["id"], entry2["id"])

if __name__ == "__main__":
    unittest.main()
