from backend.system.version import get_version

def run_migrations():
    version = get_version()

    if version == "40.1":
        print("Running migration 40_0 → 40_1")
        from migrations import 40_1
        40_1.upgrade()
