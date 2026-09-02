import sqlite3
import json
import time
from pathlib import Path

DEFAULT_DB_PATH = Path("data/kingdom.db")

class Database:

    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Tasks table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                input_json TEXT,
                assigned_knight TEXT,
                result_json TEXT,
                error TEXT,
                cancellation_requested INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # Knights table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS knights (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                capabilities_json TEXT,
                current_task TEXT,
                health TEXT NOT NULL,
                is_local INTEGER DEFAULT 1,
                last_heartbeat REAL NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # Events table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                source TEXT NOT NULL,
                task_id TEXT,
                payload_json TEXT
            )
            """)

            # Memory table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                metadata_json TEXT,
                source TEXT,
                trust REAL DEFAULT 1.0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # Runtime State table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS runtime_state (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            conn.commit()

# Global database instance
db = Database()
