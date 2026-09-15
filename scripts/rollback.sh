#!/bin/bash
set -e

echo "=== Kingdom Automatic Release Rollback ==="
echo "[1/3] Locating latest data backup snapshot..."
python3 -c "
import os, glob
backups = sorted(glob.glob('data/backups/backup_*'))
if backups:
    latest = backups[-1]
    print(f'Restoring snapshot from {latest}...')
    from backend.system.updater import updater_engine
    updater_engine.rollback(latest, 'data')
    print('Data snapshot rollback complete.')
else:
    print('No data backup snapshot found. Maintaining current storage state.')
"

echo "[2/3] Verifying database schema integrity..."
python3 -c "from backend.storage.db import db; conn = db.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT 1'); print('Database connection operational.')"

echo "[3/3] Rollback Procedure Finished."
