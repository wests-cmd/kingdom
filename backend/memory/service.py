"""Persistent graph and timeline memory for the local Kingdom runtime."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class MemoryService:
    def __init__(self, data_dir=None):
        self._data_dir = Path(data_dir or "data/memory")
        self._path = self._data_dir / "runtime.json"
        self._state = self._load()

    def add(self, content, metadata=None, weight=1.0):
        entry = {"id": str(uuid4()), "content": content, "metadata": metadata or {}, "weight": weight, "created_at": datetime.now(timezone.utc).isoformat()}
        self._state["entries"].append(entry)
        self._state["graph"]["nodes"].append({"id": entry["id"], "label": content, "weight": weight})
        self._state["timeline"].append({"timestamp": entry["created_at"], "entry_id": entry["id"]})
        self._save()
        return entry

    def record_task(self, task):
        return self.add(task["prompt"], {"task_id": task["id"], "status": task["status"], "result": task["result"]}, 1.0 if task["status"] == "completed" else 0.25)

    def search(self, query, limit=5):
        terms = set(re.findall(r"\w+", query.lower()))
        def score(entry):
            matches = len(terms.intersection(re.findall(r"\w+", entry["content"].lower())))
            return (matches, entry["weight"])
        return [entry for entry in sorted(self._state["entries"], key=score, reverse=True) if score(entry)[0]][:limit]

    def entries(self, limit=100):
        return self._state["entries"][-limit:]

    def graph(self):
        return self._state["graph"]

    def snapshot(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        path = self._data_dir.parent / "snapshots" / f"memory-{int(datetime.now().timestamp())}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        return str(path)

    def _load(self):
        if not self._path.exists():
            return {"entries": [], "timeline": [], "graph": {"nodes": [], "edges": []}}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
