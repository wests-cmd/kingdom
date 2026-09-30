"""Persistent graph and timeline memory for the local Kingdom runtime."""

from __future__ import annotations

import heapq
import json
import re
import time
from copy import deepcopy
from threading import RLock
from backend.storage.db import Database, db
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

_WORD_PATTERN = re.compile(r"\w+")


class MemoryService:
    def __init__(self, data_dir=None):
        self._data_dir = Path(data_dir or "data/memory")
        self._path = self._data_dir / "runtime.json"
        self.db = Database(self._data_dir / "memory.db") if data_dir else db
        self._lock = RLock()
        self._state = self._load()

    def add(self, content, metadata=None, weight=1.0):
        entry = {"id": str(uuid4()), "content": content, "metadata": deepcopy(metadata or {}), "weight": weight, "created_at": datetime.now(timezone.utc).isoformat()}
        with self._lock:
            previous = self._state
            self._state = deepcopy(previous)
            self._state["entries"].append(entry)
            self._state["graph"]["nodes"].append({"id": entry["id"], "label": content, "weight": weight})
            self._state["timeline"].append({"timestamp": entry["created_at"], "entry_id": entry["id"]})
            try:
                self._save()
            except Exception:
                self._state = previous
                raise
        return deepcopy(entry)

    def record_task(self, task):
        return self.add(task["prompt"], {"task_id": task["id"], "status": task["status"], "result": task["result"]}, 1.0 if task["status"] == "completed" else 0.25)

    def search(self, query, limit=5):
        # Optimization: Single-pass query matching with pre-compiled regex and heapq.nlargest extraction.
        # Avoids repeated regex tokenization and double-scoring per entry during sorting and filtering.
        if not query or not self._state["entries"]:
            return []
        terms = set(_WORD_PATTERN.findall(query.lower()))
        if not terms:
            return []

        scored_entries = []
        for entry in self._state["entries"]:
            words = set(_WORD_PATTERN.findall(entry["content"].lower()))
            matches = len(terms.intersection(words))
            if matches > 0:
                scored_entries.append((matches, entry["weight"], entry))

        if not scored_entries:
            return []

        top_entries = heapq.nlargest(limit, scored_entries, key=lambda x: (x[0], x[1]))
        return [item[2] for item in top_entries]

    def entries(self, limit=100):
        return deepcopy(self._state["entries"][-limit:])

    def graph(self):
        return deepcopy(self._state["graph"])

    def snapshot(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        path = self._data_dir.parent / "snapshots" / f"memory-{int(datetime.now().timestamp())}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        temporary.replace(path)
        return str(path)

    def _load(self):
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT value_json FROM runtime_state WHERE key='memory:graph'").fetchone()
        if row:
            return json.loads(row[0])
        state = {"entries": [], "timeline": [], "graph": {"nodes": [], "edges": []}}
        if self._path.exists():
            try:
                state = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(state.get("entries"), list) or not isinstance(state.get("graph", {}).get("nodes"), list):
                    raise ValueError("Malformed legacy memory")
            except (ValueError, UnicodeError) as exc:
                raise RuntimeError("Legacy memory is damaged; preserved original requires recovery") from exc
        with self.db.get_connection() as conn:
            conn.execute("INSERT INTO runtime_state(key,value_json,updated_at) VALUES('memory:graph',?,?) ON CONFLICT(key) DO NOTHING", (json.dumps(state), time.time()))
            conn.commit()
            return json.loads(conn.execute("SELECT value_json FROM runtime_state WHERE key='memory:graph'").fetchone()[0])

    def _save(self):
        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value_json FROM runtime_state WHERE key='memory:graph'").fetchone()
            merged = json.loads(row[0]) if row else {"entries": [], "timeline": [], "graph": {"nodes": [], "edges": []}}
            for target, incoming, identity in ((merged["entries"], self._state["entries"], "id"),
                                                (merged["timeline"], self._state["timeline"], "entry_id"),
                                                (merged["graph"]["nodes"], self._state["graph"]["nodes"], "id")):
                existing = {item[identity] for item in target}
                target.extend(item for item in incoming if item[identity] not in existing)
            conn.execute("INSERT INTO runtime_state(key,value_json,updated_at) VALUES('memory:graph',?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (json.dumps(merged), time.time()))
            conn.commit()
        self._state = merged
