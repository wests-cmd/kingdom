import time
import json
from typing import Dict, Any, List, Optional
from backend.storage.repository import memory_repo
from backend.events.event_bus import event_bus

VALID_DOMAINS = [
    "Personal",
    "Business",
    "Projects",
    "Finance",
    "Invoices",
    "Pricing",
    "Customers",
    "Engineering",
    "Workflows",
    "Skills"
]

class KnowledgeDomainManager:
    def __init__(self, repository=None):
        self.repo = repository or memory_repo

    def add_knowledge_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        item_id = item.get("id") or f"kn-item-{int(time.time() * 1000)}"
        domain = item.get("domain", "General")
        is_source_of_truth = item.get("is_source_of_truth", False)

        # Check for Source-Of-Truth Conflicts
        conflicts = []
        if is_source_of_truth:
            existing = self.repo.search(query=domain, limit=20)
            for prev in existing:
                meta = prev.get("metadata", {})
                if meta.get("domain") == domain and meta.get("is_source_of_truth"):
                    conflicts.append(prev)

        record = {
            "id": item_id,
            "content": item.get("content", ""),
            "metadata": {
                "domain": domain,
                "is_source_of_truth": is_source_of_truth,
                "owner": item.get("owner", "user"),
                "provenance": item.get("provenance", "user_input"),
                "has_conflicts": len(conflicts) > 0,
                "conflict_ids": [c["id"] for c in conflicts]
            },
            "source": item.get("source", "knowledge_manager"),
            "trust": item.get("trust", 0.95),
            "created_at": time.time()
        }

        self.repo.save(record)

        if len(conflicts) > 0:
            event_bus.publish("knowledge.conflict_detected", {
                "item_id": item_id,
                "domain": domain,
                "conflicting_ids": [c["id"] for c in conflicts]
            }, source="knowledge_domains")

        return {
            "item": record,
            "conflicts_detected": len(conflicts) > 0,
            "conflicts": conflicts
        }

knowledge_domain_manager = KnowledgeDomainManager()
