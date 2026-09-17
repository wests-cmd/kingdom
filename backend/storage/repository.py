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
        meta_json = json.dumps(task.get("metadata", {}))
        result_json = json.dumps(task.get("result")) if task.get("result") is not None else None
        created_at_val = task.get("created_at") or str(now)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO tasks (
                id, execution_id, prompt, type, status, input_json, metadata_json,
                assigned_knight, attempt, max_attempts, started_at, completed_at,
                result_json, error, cancellation_requested, version, lease_id,
                fencing_token, idempotency_key, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                execution_id=excluded.execution_id,
                prompt=excluded.prompt,
                type=excluded.type,
                status=excluded.status,
                input_json=excluded.input_json,
                metadata_json=excluded.metadata_json,
                assigned_knight=excluded.assigned_knight,
                attempt=excluded.attempt,
                max_attempts=excluded.max_attempts,
                started_at=excluded.started_at,
                completed_at=excluded.completed_at,
                result_json=excluded.result_json,
                error=excluded.error,
                cancellation_requested=excluded.cancellation_requested,
                version=excluded.version,
                lease_id=excluded.lease_id,
                fencing_token=excluded.fencing_token,
                idempotency_key=excluded.idempotency_key,
                updated_at=excluded.updated_at
            """, (
                task_id,
                task.get("execution_id"),
                task.get("prompt"),
                task.get("type", "generic"),
                task.get("status", "queued"),
                input_json,
                meta_json,
                task.get("assigned_knight"),
                task.get("attempt", 0),
                task.get("max_attempts", 1),
                task.get("started_at"),
                task.get("completed_at"),
                result_json,
                task.get("error"),
                1 if task.get("cancellation_requested") else 0,
                task.get("version", 1),
                task.get("lease_id"),
                task.get("fencing_token", 0),
                task.get("idempotency_key"),
                created_at_val,
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
                cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC LIMIT ?", (status, limit))
            else:
                cursor.execute("SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row):
        keys = row.keys()
        return {
            "id": row["id"],
            "execution_id": row["execution_id"] if "execution_id" in keys else None,
            "prompt": row["prompt"] if "prompt" in keys else None,
            "type": row["type"],
            "status": row["status"],
            "input": json.loads(row["input_json"]) if "input_json" in keys and row["input_json"] else {},
            "metadata": json.loads(row["metadata_json"]) if "metadata_json" in keys and row["metadata_json"] else {},
            "assigned_knight": row["assigned_knight"],
            "attempt": row["attempt"] if "attempt" in keys and row["attempt"] is not None else 0,
            "max_attempts": row["max_attempts"] if "max_attempts" in keys and row["max_attempts"] is not None else 1,
            "started_at": row["started_at"] if "started_at" in keys else None,
            "completed_at": row["completed_at"] if "completed_at" in keys else None,
            "result": json.loads(row["result_json"]) if "result_json" in keys and row["result_json"] else None,
            "error": row["error"],
            "cancellation_requested": bool(row["cancellation_requested"]),
            "version": row["version"] if "version" in keys and row["version"] is not None else 1,
            "lease_id": row["lease_id"] if "lease_id" in keys else None,
            "fencing_token": row["fencing_token"] if "fencing_token" in keys and row["fencing_token"] is not None else 0,
            "idempotency_key": row["idempotency_key"] if "idempotency_key" in keys else None,
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
        granted_caps_json = json.dumps(knight.get("granted_capabilities", []))
        pub_ident_json = json.dumps(knight.get("public_identity")) if knight.get("public_identity") else None
        conn_meta_json = json.dumps(knight.get("connection_metadata", {}))
        hw_prof_json = json.dumps(knight.get("hardware_profile", {}))

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO knights (
                id, role, status, node_state, capabilities_json, granted_capabilities_json,
                current_task, health, is_local, last_heartbeat, public_identity_json,
                fingerprint, kingdom_id, connection_metadata_json, hardware_profile_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                role=excluded.role,
                status=excluded.status,
                node_state=excluded.node_state,
                capabilities_json=excluded.capabilities_json,
                granted_capabilities_json=excluded.granted_capabilities_json,
                current_task=excluded.current_task,
                health=excluded.health,
                is_local=excluded.is_local,
                last_heartbeat=excluded.last_heartbeat,
                public_identity_json=excluded.public_identity_json,
                fingerprint=excluded.fingerprint,
                kingdom_id=excluded.kingdom_id,
                connection_metadata_json=excluded.connection_metadata_json,
                hardware_profile_json=excluded.hardware_profile_json,
                updated_at=excluded.updated_at
            """, (
                knight_id,
                knight.get("role", "knight"),
                knight.get("status", "idle"),
                knight.get("node_state", "CONNECTED"),
                caps_json,
                granted_caps_json,
                knight.get("current_task"),
                knight.get("health", "healthy"),
                1 if knight.get("is_local", True) else 0,
                knight.get("last_heartbeat", now),
                pub_ident_json,
                knight.get("fingerprint"),
                knight.get("kingdom_id"),
                conn_meta_json,
                hw_prof_json,
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
            "node_state": row["node_state"] if "node_state" in row.keys() else "CONNECTED",
            "capabilities": json.loads(row["capabilities_json"]) if row["capabilities_json"] else [],
            "granted_capabilities": json.loads(row["granted_capabilities_json"]) if "granted_capabilities_json" in row.keys() and row["granted_capabilities_json"] else [],
            "current_task": row["current_task"],
            "health": row["health"],
            "is_local": bool(row["is_local"]),
            "last_heartbeat": row["last_heartbeat"],
            "public_identity": json.loads(row["public_identity_json"]) if "public_identity_json" in row.keys() and row["public_identity_json"] else None,
            "fingerprint": row["fingerprint"] if "fingerprint" in row.keys() else None,
            "kingdom_id": row["kingdom_id"] if "kingdom_id" in row.keys() else None,
            "connection_metadata": json.loads(row["connection_metadata_json"]) if "connection_metadata_json" in row.keys() and row["connection_metadata_json"] else {},
            "hardware_profile": json.loads(row["hardware_profile_json"]) if "hardware_profile_json" in row.keys() and row["hardware_profile_json"] else {},
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
