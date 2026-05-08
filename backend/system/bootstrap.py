from backend.system.migrator import run_migrations
from backend.runtime.engine import RuntimeEngine
from backend.system.health import health_check

def bootstrap():
    print("Booting Kingdom...")

    health_check()
    run_migrations()

    engine = RuntimeEngine()
    engine.initialize()

    print("Kingdom Online")
