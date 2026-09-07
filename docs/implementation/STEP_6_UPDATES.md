# STEP 6 ARCHITECTURE: APP UPDATES & MIGRATION READINESS

Kingdom Desktop and Core Runtime support safe, non-destructive version updates and migrations.

## Update Pipeline
1. `GET /api/system/version` returns running version (`v40.2.0`), release channel, and system architecture.
2. Installer verifies signature before applying updates.
3. Database migrations in `backend/storage/db.py` inspect SQLite schema (`PRAGMA table_info`) and apply non-destructive column additions.
4. System performs health checks (`/health/ready`) before finalizing update.
