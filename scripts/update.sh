#!/bin/bash
set -e

echo "=== Kingdom Release Updater ==="
echo "[1/4] Checking release manifest & checksums..."
python3 -c "from backend.system.updater import updater_engine; res = updater_engine.check_updates(); print(f'Current: {res[\"current_version\"]}, Latest: {res[\"latest_version\"]}')"

echo "[2/4] Executing database schema migrations..."
python3 -c "from backend.system.migrator import run_migrations; run_migrations()"

echo "[3/4] Running health readiness verification..."
python3 -c "from backend.system.health import check_system_health; print('Health check OK:', check_system_health())"

echo "[4/4] Kingdom Update Complete."
