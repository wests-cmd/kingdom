import importlib.util
from pathlib import Path

from backend.system.version import get_version


def _run_migration(filename):
    path = Path(__file__).resolve().parents[2] / "migrations" / filename
    spec = importlib.util.spec_from_file_location(path.stem.replace("_", ""), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()

MIGRATION_REGISTRY = {
    "40.1.0": "40_1.py",
    "40.2.0": "40_1.py"
}

def run_migrations():
    version = get_version()
    migration_file = MIGRATION_REGISTRY.get(version)

    if migration_file:
        print(f"[Migrator] Running migration script {migration_file} for version {version}")
        _run_migration(migration_file)
    else:
        print(f"[Migrator] Schema is up to date for version {version}")
