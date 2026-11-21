"""SQLite concurrency: revocation/audit writes must not wait on status readers.

This is a deterministic database-lock regression, not proof of physical Windows
deployment. It runs with the same Database class used by the API, node registry,
event repository and RPC replay ledger.
"""
from __future__ import annotations

import threading

from backend.storage.db import Database


def test_writer_commit_does_not_wait_for_open_reader(tmp_path):
    database = Database(tmp_path / "cluster.sqlite")
    with database.get_connection() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"

    started = threading.Event()
    completed = threading.Event()
    errors = []

    # A realistic status reader holds a snapshot while a concurrent
    # authorization/revocation worker writes. Without WAL, its commit waits.
    reader = database.get_connection()
    worker = None
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM runtime_state").fetchone()

        def write_event():
            started.set()
            try:
                with database.get_connection() as connection:
                    connection.execute(
                        "INSERT INTO runtime_state(key,value_json,updated_at) "
                        "VALUES(?,?,?)",
                        ("revocation:concurrency-test", '{"state":"revoked"}', 1.0),
                    )
                    connection.commit()
            except Exception as exc:
                errors.append(exc)
            finally:
                completed.set()

        worker = threading.Thread(target=write_event, daemon=True)
        worker.start()
        assert started.wait(2.0), "Writer never started"
        # A rollback-journal writer cannot commit while the reader holds a
        # SHARED lock; WAL guarantees the writer can commit independently.
        assert completed.wait(3.0), "Writer blocked behind an open reader"
        assert errors == [], errors
        assert reader.execute(
            "SELECT COUNT(*) FROM runtime_state"
        ).fetchone()[0] == 0, "Reader snapshot changed mid-transaction"
        reader.rollback()
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT value_json FROM runtime_state WHERE key=?",
                ("revocation:concurrency-test",),
            ).fetchone()
        assert row is not None and "revoked" in row[0]
    finally:
        reader.rollback()
        reader.close()
        if worker is not None:
            worker.join(timeout=6.0)


def test_journal_mode_persists_across_database_reopen(tmp_path):
    path = tmp_path / "cluster.sqlite"
    db_a = Database(path)
    with db_a.get_connection() as conn:
        conn.execute(
            "INSERT INTO runtime_state(key,value_json,updated_at) VALUES(?,?,?)",
            ("durability", '{"ok":true}', 1.0),
        )
        conn.commit()
    db_b = Database(path)
    with db_b.get_connection() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute(
            "SELECT value_json FROM runtime_state WHERE key='durability'"
        ).fetchone()[0] == '{"ok":true}'
