"""Durable adapter records in Kingdom's existing SQLite database."""
import json
import time
from backend.storage.db import db


class IntegrationRepository:
    def __init__(self, database=None):
        self.db = database or db
        with self.db.get_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS integration_records (
                kind TEXT NOT NULL, id TEXT NOT NULL, value_json TEXT NOT NULL,
                updated_at REAL NOT NULL, PRIMARY KEY(kind,id))""")

    def put(self, kind, record_id, value):
        with self.db.get_connection() as conn:
            conn.execute("""INSERT INTO integration_records VALUES(?,?,?,?)
                ON CONFLICT(kind,id) DO UPDATE SET value_json=excluded.value_json,
                updated_at=excluded.updated_at""", (kind, record_id, json.dumps(value), time.time()))

    def get(self, kind, record_id):
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT value_json FROM integration_records WHERE kind=? AND id=?", (kind, record_id)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind):
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT value_json FROM integration_records WHERE kind=? ORDER BY updated_at,id", (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def delete(self, kind, record_id):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM integration_records WHERE kind=? AND id=?", (kind, record_id))
