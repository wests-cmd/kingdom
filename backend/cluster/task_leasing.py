"""Durable task leases with transactional, exact monotonic fencing."""
import secrets
import time
import math
from threading import RLock
from typing import Optional
from pydantic import BaseModel, Field
from backend.storage.db import db

class TaskLease(BaseModel):
    lease_id: str = Field(default_factory=lambda: f"lease_{secrets.token_hex(12)}")
    task_id: str
    assigned_node_id: str
    fencing_token: int
    capability_scope: str
    issued_at: float = Field(default_factory=time.time)
    expires_at: float
    revoked: bool = False

class TaskLeaseManager:
    def __init__(self, default_lease_ttl_sec=60.0, database=None):
        self.default_ttl = default_lease_ttl_sec
        self.db = database or db
        self.leases = {}
        self.fencing_sequence = {}
        self._lock = RLock()
        self._load_persisted_leases()

    @staticmethod
    def _from_row(row):
        return TaskLease(lease_id=row["lease_id"], task_id=row["task_id"],
            assigned_node_id=row["node_id"], fencing_token=row["fencing_token"],
            capability_scope=row["capability_scope"], issued_at=row["issued_at"],
            expires_at=row["expires_at"], revoked=bool(row["revoked"]))

    def _load_persisted_leases(self):
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM leases ORDER BY fencing_token ASC").fetchall()
        for row in rows:
            lease = self._from_row(row)
            self.leases[lease.task_id] = lease
            self.fencing_sequence[lease.task_id] = lease.fencing_token

    def _save_lease(self, lease):
        with self.db.get_connection() as conn:
            conn.execute("""INSERT INTO leases
                (lease_id, task_id, node_id, fencing_token, capability_scope, issued_at, expires_at, revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lease_id) DO UPDATE SET revoked=excluded.revoked, expires_at=excluded.expires_at""",
                (lease.lease_id, lease.task_id, lease.assigned_node_id, lease.fencing_token,
                 lease.capability_scope, lease.issued_at, lease.expires_at, int(lease.revoked)))
            conn.commit()

    def issue_lease(self, task_id, assigned_node_id, capability_scope, ttl_sec: Optional[float] = None):
        ttl = self.default_ttl if ttl_sec is None else ttl_sec
        if not math.isfinite(ttl) or ttl <= 0:
            raise ValueError("Lease lifetime must be positive")
        with self._lock, self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if self._node_busy(conn, assigned_node_id, task_id):
                raise ValueError("Node already has an active task lease")
            seq = conn.execute("SELECT coalesce(max(fencing_token), 0)+1 FROM leases WHERE task_id=?", (task_id,)).fetchone()[0]
            lease = TaskLease(task_id=task_id, assigned_node_id=assigned_node_id,
                fencing_token=seq, capability_scope=capability_scope, expires_at=time.time()+ttl)
            conn.execute("UPDATE leases SET revoked=1 WHERE task_id=?", (task_id,))
            conn.execute("""INSERT INTO leases
                (lease_id, task_id, node_id, fencing_token, capability_scope, issued_at, expires_at, revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (lease.lease_id, task_id, assigned_node_id, seq, capability_scope, lease.issued_at, lease.expires_at))
            conn.commit()
        self.leases[task_id] = lease
        self.fencing_sequence[task_id] = seq
        return lease

    def issue_and_claim(self, task_id, assigned_node_id, capability_scope, expected_version):
        """Atomically reserve one node slot and claim a queued task.

        BEGIN IMMEDIATE serializes competing managers, including separate
        processes. The persisted lease, rather than a manager's cache, owns
        capacity until revocation or expiry.
        """
        if not math.isfinite(self.default_ttl) or self.default_ttl <= 0:
            raise ValueError("Lease lifetime must be positive")
        with self._lock, self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if self._node_busy(conn, assigned_node_id, task_id):
                return None
            seq = conn.execute("SELECT coalesce(max(fencing_token),0)+1 FROM leases WHERE task_id=?", (task_id,)).fetchone()[0]
            lease = TaskLease(task_id=task_id, assigned_node_id=assigned_node_id, fencing_token=seq,
                              capability_scope=capability_scope, expires_at=time.time()+self.default_ttl)
            updated = conn.execute("UPDATE tasks SET status='leased',assigned_knight=?,lease_id=?,fencing_token=?,attempt=attempt+1,version=version+1,started_at=?,updated_at=? WHERE id=? AND lower(status)='queued' AND version=?",
                                   (assigned_node_id, lease.lease_id, seq, str(time.time()), time.time(), task_id, expected_version))
            if updated.rowcount != 1:
                return None
            conn.execute("UPDATE leases SET revoked=1 WHERE task_id=?", (task_id,))
            conn.execute("INSERT INTO leases(lease_id,task_id,node_id,fencing_token,capability_scope,issued_at,expires_at,revoked) VALUES(?,?,?,?,?,?,?,0)",
                         (lease.lease_id, task_id, assigned_node_id, seq, capability_scope, lease.issued_at, lease.expires_at))
            conn.commit()
        self.leases[task_id] = lease
        self.fencing_sequence[task_id] = seq
        return lease

    @staticmethod
    def _node_busy(conn, node_id, replacing_task_id):
        # Called only inside a write transaction: checking and inserting must
        # never be separated or two independent managers can overbook a node.
        return conn.execute(
            "SELECT 1 FROM leases WHERE node_id=? AND task_id<>? "
            "AND revoked=0 AND expires_at>? LIMIT 1",
            (node_id, replacing_task_id, time.time()),
        ).fetchone() is not None

    def busy_node_ids(self):
        """Scheduling hint; issue_and_claim remains the atomic authority."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT node_id FROM leases WHERE revoked=0 AND expires_at>?",
                (time.time(),),
            ).fetchall()
        return {row["node_id"] for row in rows}

    def validate_lease_execution(self, task_id, node_id, fencing_token):
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM leases WHERE task_id=? ORDER BY fencing_token DESC LIMIT 1", (task_id,)).fetchone()
        if not row:
            raise PermissionError("No active task lease")
        lease = self._from_row(row)
        self.leases[task_id] = lease
        if lease.revoked or time.time() >= lease.expires_at:
            raise PermissionError("Task lease has expired or was revoked")
        if lease.assigned_node_id != node_id:
            raise PermissionError("Node mismatch for task lease")
        if type(fencing_token) is not int or fencing_token != lease.fencing_token:
            raise PermissionError("Fencing token error: must exactly match the active lease")
        return True

    def revoke_lease(self, task_id):
        with self.db.get_connection() as conn:
            conn.execute("UPDATE leases SET revoked=1 WHERE task_id=?", (task_id,))
            conn.commit()
        if task_id in self.leases:
            self.leases[task_id].revoked = True

task_lease_manager = TaskLeaseManager()
