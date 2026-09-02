import unittest
from backend.memory.persistence import MemoryStore

class TestMemoryStore(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()

    def test_memory_add_and_search(self):
        rec = self.store.add_memory("Unique secret codebase architecture note", metadata={"category": "audit"})
        self.assertIsNotNone(rec["id"])

        results = self.store.search_memory("codebase architecture")
        self.assertTrue(len(results) >= 1)
        self.assertIn("Unique secret codebase", results[0]["content"])

if __name__ == "__main__":
    unittest.main()
