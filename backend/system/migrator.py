"""Apply the idempotent runtime schema migration used by fresh and existing installs."""
from backend.storage.db import db
from backend.system.version import get_version

MIGRATION_REGISTRY = {"1.0.0": "runtime_schema_v1"}

def run_migrations():
    db.init_db()
    return {"version":get_version(), "schema":"runtime_schema_v1", "status":"applied"}
