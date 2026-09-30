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
                node_state TEXT DEFAULT 'CONNECTED',
                capabilities_json TEXT,
                granted_capabilities_json TEXT,
                current_task TEXT,
                health TEXT NOT NULL,
                is_local INTEGER DEFAULT 1,
                last_heartbeat REAL NOT NULL,
                public_identity_json TEXT,
                fingerprint TEXT,
                kingdom_id TEXT,
                connection_metadata_json TEXT,
                hardware_profile_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # Schema migration check for tasks columns
            cursor.execute("PRAGMA table_info(tasks)")
            task_cols = [col[1] for col in cursor.fetchall()]
            for col_name, col_def in [
                ("execution_id", "TEXT"),
                ("prompt", "TEXT"),
                ("metadata_json", "TEXT"),
                ("attempt", "INTEGER DEFAULT 0"),
                ("max_attempts", "INTEGER DEFAULT 1"),
                ("started_at", "TEXT"),
                ("completed_at", "TEXT"),
                ("version", "INTEGER DEFAULT 1"),
                ("lease_id", "TEXT"),
                ("fencing_token", "INTEGER DEFAULT 0"),
                ("idempotency_key", "TEXT")
            ]:
                if col_name not in task_cols:
                    cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_def}")

            # Schema migration check for knights columns
            cursor.execute("PRAGMA table_info(knights)")
            columns = [column[1] for column in cursor.fetchall()]
            if "node_state" not in columns:
                cursor.execute("ALTER TABLE knights ADD COLUMN node_state TEXT DEFAULT 'CONNECTED'")
            if "granted_capabilities_json" not in columns:
                cursor.execute("ALTER TABLE knights ADD COLUMN granted_capabilities_json TEXT")
            if "public_identity_json" not in columns:
                cursor.execute("ALTER TABLE knights ADD COLUMN public_identity_json TEXT")
            if "fingerprint" not in columns:
                cursor.execute("ALTER TABLE knights ADD COLUMN fingerprint TEXT")
            if "kingdom_id" not in columns:
                cursor.execute("ALTER TABLE knights ADD COLUMN kingdom_id TEXT")
            if "connection_metadata_json" not in columns:
                cursor.execute("ALTER TABLE knights ADD COLUMN connection_metadata_json TEXT")
            if "hardware_profile_json" not in columns:
                cursor.execute("ALTER TABLE knights ADD COLUMN hardware_profile_json TEXT")

            # Leases table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS leases (
                lease_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                fencing_token INTEGER NOT NULL,
                capability_scope TEXT,
                issued_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                revoked INTEGER DEFAULT 0
            )
            """)

            # RPC Replay Protection table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS rpc_replay (
                msg_id TEXT PRIMARY KEY,
                sender_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                expires_at REAL NOT NULL
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

            # Profiles table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT,
                system INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                version INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # Capabilities table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS capabilities (
                id TEXT PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                risk_level TEXT DEFAULT 'low',
                requires_auth INTEGER DEFAULT 0,
                requires_approval INTEGER DEFAULT 0,
                read_only INTEGER DEFAULT 1,
                enabled INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # Profile Capabilities mapping
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_capabilities (
                profile_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                required INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'recommend',
                created_at REAL NOT NULL,
                PRIMARY KEY (profile_id, capability_id)
            )
            """)

            # User Profiles
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                name TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                is_default INTEGER DEFAULT 0,
                preferences_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # API Providers table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_providers (
                id TEXT PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                homepage_url TEXT,
                documentation_url TEXT,
                source TEXT NOT NULL,
                category TEXT,
                auth_type TEXT DEFAULT 'none',
                https_supported INTEGER DEFAULT 1,
                cors_support TEXT DEFAULT 'unknown',
                free_access TEXT DEFAULT 'unknown',
                status TEXT DEFAULT 'discovered',
                last_verified_at REAL,
                verification_status TEXT DEFAULT 'unverified',
                metadata_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # API Capabilities mapping
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_capabilities (
                api_provider_id TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                mapping_source TEXT DEFAULT 'catalog',
                verified INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                PRIMARY KEY (api_provider_id, capability_id)
            )
            """)

            # Catalog Syncs log table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_catalog_syncs (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                started_at REAL NOT NULL,
                completed_at REAL,
                entries_seen INTEGER DEFAULT 0,
                entries_added INTEGER DEFAULT 0,
                entries_updated INTEGER DEFAULT 0,
                entries_disabled INTEGER DEFAULT 0,
                errors TEXT,
                status TEXT DEFAULT 'pending',
                source_checksum TEXT
            )
            """)

            # API Verifications log table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_verifications (
                id TEXT PRIMARY KEY,
                api_provider_id TEXT NOT NULL,
                checked_at REAL NOT NULL,
                reachable INTEGER DEFAULT 0,
                https_valid INTEGER DEFAULT 0,
                documentation_reachable INTEGER DEFAULT 0,
                auth_detected TEXT,
                response_time_ms REAL,
                error TEXT
            )
            """)

            conn.commit()

# Global database instance
db = Database()
