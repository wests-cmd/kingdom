#!/usr/bin/env python3
import os
import sys
import platform
import time
import json
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

INSTALL_LOG = Path("data/logs/install.log")

def log_installer(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        INSTALL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(INSTALL_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def run_health_check():
    log_installer("Running post-installation health check...")
    try:
        from backend.runtime.engine import runtime_engine
        st = runtime_engine.status()
        log_installer(f"Health check PASSED: Engine status = {st}")
        return True
    except Exception as e:
        log_installer(f"Health check FAILED: {e}")
        return False

def main():
    print("=" * 60)
    print(" 👑 KINGDOM UNIVERSAL RUNTIME INSTALLER v40.1")
    print("=" * 60)

    system_os = platform.system()
    arch = platform.machine()
    py_ver = platform.python_version()

    log_installer(f"Detected Platform: OS={system_os}, Arch={arch}, Python={py_ver}")

    non_interactive = "--non-interactive" in sys.argv

    if non_interactive:
        install_dir = "./data"
        selected_mode = "Personal"
    else:
        try:
            install_dir = input("Where should Kingdom store persistent state? [default: ./data]: ").strip() or "./data"
            install_mode = input("Choose installation mode (1. Personal, 2. Server, 3. Custom) [default: 1]: ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            install_dir = "./data"
            install_mode = "1"
        mode_map = {"1": "Personal", "2": "Server", "3": "Custom"}
        selected_mode = mode_map.get(install_mode, "Personal")

    log_installer(f"Configuring Kingdom: DataDir={install_dir}, Mode={selected_mode}")

    # Initialize SQLite storage & tables
    try:
        from backend.storage.db import db
        from backend.skills.skill_engine import skill_engine
        log_installer("Initializing SQLite storage engine & database schemas...")
        db.init_db()
        skill_engine.init_builtin_skills()
        log_installer("Database schema & builtin skills successfully initialized.")
    except Exception as e:
        log_installer(f"ERROR initializing database: {e}")
        sys.exit(1)

    # Health check
    success = run_health_check()
    print("=" * 60)
    if success:
        log_installer("SUCCESS: Kingdom v40.1 installed successfully.")
        print("\nTo start Kingdom:")
        print("  uvicorn backend.main:app --reload")
        print("  cd frontend && npm run dev\n")
    else:
        log_installer("WARNING: Kingdom installation completed with warnings.")

if __name__ == "__main__":
    main()
