import time
import uuid
from typing import Optional, Dict, Any, List
from backend.storage.repository import memory_repo

class MemoryStore:

    def __init__(self, repository=None):
        self.repo = repository or memory_repo

    def add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "user",
        trust: float = 1.0
    ) -> Dict[str, Any]:
        rec_id = str(uuid.uuid4())
        now = time.time()

        record = {
            "id": rec_id,
            "content": content,
            "metadata": metadata or {},
            "source": source,
            "trust": trust,
            "created_at": now,
            "updated_at": now
        }

        self.repo.save(record)
        return record

    def search_memory(self, query: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return self.repo.search(query=query, limit=limit)

# Global memory store instance
memory_store = MemoryStore()
