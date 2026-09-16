import time
import secrets
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.storage.db import db


class TaskLease(BaseModel):
    lease_id: str = Field(default_factory=lambda: f"lease_{secrets.token_hex(6)}")
    task_id: str
    assigned_node_id: str
    fencing_token: int  # Monotonically increasing fencing sequence
    capability_scope: str
    issued_at: float = Field(default_factory=time.time)
    expires_at: float
    revoked: bool = False


class TaskLeaseManager:

    def __init__(self, default_lease_ttl_sec: float = 60.0, database=None):
        self.default_ttl = default_lease_ttl_sec
        self.db = database or db
        self.leases: Dict[str, TaskLease] = {}  # task_id -> active TaskLease
        self.fencing_sequence: Dict[str, int] = {}  # task_id -> current max fencing token
        self._load_persisted_leases()

    def _load_persisted_leases(self):
        try:
            now = time.time()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM leases WHERE revoked = 0 AND expires_at > ?", (now,))
                rows = cursor.fetchall()
                for r in rows:
                    lease = TaskLease(
                        lease_id=r["lease_id"],
                        task_id=r["task_id"],
                        assigned_node_id=r["node_id"],
                        fencing_token=r["fencing_token"],
                        capability_scope=r["capability_scope"] or "compute",
                        issued_at=r["issued_at"],
                        expires_at=r["expires_at"],
                        revoked=bool(r["revoked"])
                    )
                    self.leases[r["task_id"]] = lease
                    self.fencing_sequence[r["task_id"]] = max(
                        self.fencing_sequence.get(r["task_id"], 0), r["fencing_token"]
                    )
        except Exception:
            pass

    def _save_lease(self, lease: TaskLease):
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO leases (lease_id, task_id, node_id, fencing_token, capability_scope, issued_at, expires_at, revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lease_id) DO UPDATE SET
                    revoked=excluded.revoked,
                    expires_at=excluded.expires_at
                """, (
                    lease.lease_id,
                    lease.task_id,
                    lease.assigned_node_id,
                    lease.fencing_token,
                    lease.capability_scope,
                    lease.issued_at,
                    lease.expires_at,
                    1 if lease.revoked else 0
                ))
                conn.commit()
        except Exception:
            pass

    def issue_lease(
        self,
        task_id: str,
        assigned_node_id: str,
        capability_scope: str,
        ttl_sec: Optional[float] = None
    ) -> TaskLease:
        now = time.time()
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl

        # Increment fencing token sequence for this task
        seq = self.fencing_sequence.get(task_id, 0) + 1
        self.fencing_sequence[task_id] = seq

        # Invalidate any prior lease for this task
        if task_id in self.leases:
            self.leases[task_id].revoked = True
            self._save_lease(self.leases[task_id])

        lease = TaskLease(
            task_id=task_id,
            assigned_node_id=assigned_node_id,
            fencing_token=seq,
            capability_scope=capability_scope,
            issued_at=now,
            expires_at=now + ttl
        )
        self.leases[task_id] = lease
        self._save_lease(lease)
        return lease

    def validate_lease_execution(
        self,
        task_id: str,
        node_id: str,
        fencing_token: int
    ) -> bool:
        lease = self.leases.get(task_id)
        if not lease:
            raise PermissionError(f"No active task lease found for task '{task_id}'.")

        if lease.revoked:
            raise PermissionError(f"Task lease for task '{task_id}' was revoked/superseded.")

        if time.time() > lease.expires_at:
            lease.revoked = True
            self._save_lease(lease)
            raise PermissionError(f"Task lease for task '{task_id}' has expired.")

        if lease.assigned_node_id != node_id:
            raise PermissionError(
                f"Node mismatch: Task '{task_id}' is leased to node '{lease.assigned_node_id}', got '{node_id}'."
            )

        if fencing_token < lease.fencing_token:
            raise PermissionError(
                f"Fencing token error: Stale execution request (Token {fencing_token} < Active {lease.fencing_token}). Execution blocked."
            )

        return True

    def revoke_lease(self, task_id: str) -> None:
        lease = self.leases.get(task_id)
        if lease:
            lease.revoked = True
            self._save_lease(lease)
