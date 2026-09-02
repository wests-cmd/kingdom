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

def run_migrations():
    version = get_version()

    if version == "40.1":
        print("Running migration 40_0 to 40_1")
        _run_migration("40_1.py")
