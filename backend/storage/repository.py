import json
import time
from backend.storage.db import db

class TaskRepository:

    def __init__(self, database=None):
        self.db = database or db

    def save(self, task):
        task_id = task["id"]
        now = time.time()
        input_json = json.dumps(task.get("input", {}))
        result_json = json.dumps(task.get("result")) if task.get("result") is not None else None

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO tasks (id, type, status, input_json, assigned_knight, result_json, error, cancellation_requested, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                status=excluded.status,
                input_json=excluded.input_json,
                assigned_knight=excluded.assigned_knight,
                result_json=excluded.result_json,
                error=excluded.error,
                cancellation_requested=excluded.cancellation_requested,
                updated_at=excluded.updated_at
            """, (
                task_id,
                task.get("type", "generic"),
                task.get("status", "queued"),
                input_json,
                task.get("assigned_knight"),
                result_json,
                task.get("error"),
                1 if task.get("cancellation_requested") else 0,
                task.get("created_at", now),
                now
            ))
            conn.commit()

    def get(self, task_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def list_all(self, status=None, limit=100):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit))
            else:
                cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row):
        return {
            "id": row["id"],
            "type": row["type"],
            "status": row["status"],
            "input": json.loads(row["input_json"]) if row["input_json"] else {},
            "assigned_knight": row["assigned_knight"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"],
            "cancellation_requested": bool(row["cancellation_requested"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }


class KnightRepository:

    def __init__(self, database=None):
        self.db = database or db

    def save(self, knight):
        knight_id = knight["id"]
        now = time.time()
        caps_json = json.dumps(knight.get("capabilities", []))

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO knights (id, role, status, capabilities_json, current_task, health, is_local, last_heartbeat, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                role=excluded.role,
                status=excluded.status,
                capabilities_json=excluded.capabilities_json,
                current_task=excluded.current_task,
                health=excluded.health,
                is_local=excluded.is_local,
                last_heartbeat=excluded.last_heartbeat,
                updated_at=excluded.updated_at
            """, (
                knight_id,
                knight.get("role", "knight"),
                knight.get("status", "idle"),
                caps_json,
                knight.get("current_task"),
                knight.get("health", "healthy"),
                1 if knight.get("is_local", True) else 0,
                knight.get("last_heartbeat", now),
                knight.get("created_at", now),
                now
            ))
            conn.commit()

    def get(self, knight_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM knights WHERE id = ?", (knight_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def list_all(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM knights ORDER BY id ASC")
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row):
        return {
            "id": row["id"],
            "role": row["role"],
            "status": row["status"],
            "capabilities": json.loads(row["capabilities_json"]) if row["capabilities_json"] else [],
            "current_task": row["current_task"],
            "health": row["health"],
            "is_local": bool(row["is_local"]),
            "last_heartbeat": row["last_heartbeat"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }


class EventRepository:

    def __init__(self, database=None):
        self.db = database or db

    def save(self, event):
        event_id = event["event_id"]
        payload_json = json.dumps(event.get("payload", {}))

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO events (event_id, event_type, timestamp, source, task_id, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO NOTHING
            """, (
                event_id,
                event["event_type"],
                event.get("timestamp", time.time()),
                event.get("source", "system"),
                event.get("task_id"),
                payload_json
            ))
            conn.commit()

    def query(self, task_id=None, event_type=None, limit=100):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query_str = "SELECT * FROM events"
            params = []
            conditions = []

            if task_id:
                conditions.append("task_id = ?")
                params.append(task_id)
            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)

            if conditions:
                query_str += " WHERE " + " AND ".join(conditions)

            query_str += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query_str, params)
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row):
        return {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "timestamp": row["timestamp"],
            "source": row["source"],
            "task_id": row["task_id"],
            "payload": json.loads(row["payload_json"]) if row["payload_json"] else {}
        }


class MemoryRepository:

    def __init__(self, database=None):
        self.db = database or db

    def save(self, record):
        rec_id = record["id"]
        now = time.time()
        meta_json = json.dumps(record.get("metadata", {}))

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO memory (id, content, metadata_json, source, trust, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content=excluded.content,
                metadata_json=excluded.metadata_json,
                source=excluded.source,
                trust=excluded.trust,
                updated_at=excluded.updated_at
            """, (
                rec_id,
                record["content"],
                meta_json,
                record.get("source", "user"),
                record.get("trust", 1.0),
                record.get("created_at", now),
                now
            ))
            conn.commit()

    def search(self, query=None, limit=50):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if query:
                cursor.execute("""
                SELECT * FROM memory WHERE content LIKE ? OR metadata_json LIKE ?
                ORDER BY created_at DESC LIMIT ?
                """, (f"%{query}%", f"%{query}%", limit))
            else:
                cursor.execute("SELECT * FROM memory ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row):
        return {
            "id": row["id"],
            "content": row["content"],
            "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            "source": row["source"],
            "trust": row["trust"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }


# Global repository instances
task_repo = TaskRepository()
knight_repo = KnightRepository()
event_repo = EventRepository()
memory_repo = MemoryRepository()
