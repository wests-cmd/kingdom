import json
import time
from backend.storage.db import db

class SkillRepository:

    def __init__(self, database=None):
        self.db = database or db
        self._init_tables()

    def _init_tables(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                version TEXT,
                provider TEXT,
                state TEXT NOT NULL,
                department TEXT,
                processes_json TEXT,
                dependencies_json TEXT,
                capabilities_json TEXT,
                trust_status TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS skill_bundles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                skill_ids_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """)
            conn.commit()

    def save_skill(self, skill):
        now = time.time()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO skills (id, name, description, version, provider, state, department, processes_json, dependencies_json, capabilities_json, trust_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                version=excluded.version,
                provider=excluded.provider,
                state=excluded.state,
                department=excluded.department,
                processes_json=excluded.processes_json,
                dependencies_json=excluded.dependencies_json,
                capabilities_json=excluded.capabilities_json,
                trust_status=excluded.trust_status,
                updated_at=excluded.updated_at
            """, (
                skill["id"],
                skill["name"],
                skill.get("description", ""),
                skill.get("version", "1.0.0"),
                skill.get("provider", "local"),
                skill.get("state", "saved"),
                skill.get("department", "General"),
                json.dumps(skill.get("processes", [])),
                json.dumps(skill.get("dependencies", {})),
                json.dumps(skill.get("capabilities", [])),
                skill.get("trust_status", "verified"),
                skill.get("created_at", now),
                now
            ))
            conn.commit()

    def get_skill(self, skill_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_skill(row)

    def list_skills(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skills ORDER BY name ASC")
            rows = cursor.fetchall()
            return [self._row_to_skill(r) for r in rows]

    def delete_skill(self, skill_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
            conn.commit()

    def save_bundle(self, bundle):
        now = time.time()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO skill_bundles (id, name, description, skill_ids_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                skill_ids_json=excluded.skill_ids_json,
                updated_at=excluded.updated_at
            """, (
                bundle["id"],
                bundle["name"],
                bundle.get("description", ""),
                json.dumps(bundle.get("skill_ids", [])),
                bundle.get("created_at", now),
                now
            ))
            conn.commit()

    def get_bundle(self, bundle_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skill_bundles WHERE id = ?", (bundle_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_bundle(row)

    def list_bundles(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skill_bundles ORDER BY name ASC")
            rows = cursor.fetchall()
            return [self._row_to_bundle(r) for r in rows]

    def delete_bundle(self, bundle_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM skill_bundles WHERE id = ?", (bundle_id,))
            conn.commit()

    def _row_to_skill(self, row):
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "version": row["version"],
            "provider": row["provider"],
            "state": row["state"],
            "department": row["department"],
            "processes": json.loads(row["processes_json"]) if row["processes_json"] else [],
            "dependencies": json.loads(row["dependencies_json"]) if row["dependencies_json"] else {},
            "capabilities": json.loads(row["capabilities_json"]) if row["capabilities_json"] else [],
            "trust_status": row["trust_status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def _row_to_bundle(self, row):
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "skill_ids": json.loads(row["skill_ids_json"]) if row["skill_ids_json"] else [],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

# Global repository instance
skill_repo = SkillRepository()
