import time
import secrets
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


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

    def __init__(self, default_lease_ttl_sec: float = 60.0):
        self.default_ttl = default_lease_ttl_sec
        self.leases: Dict[str, TaskLease] = {}  # task_id -> active TaskLease
        self.fencing_sequence: Dict[str, int] = {}  # task_id -> current max fencing token

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

        lease = TaskLease(
            task_id=task_id,
            assigned_node_id=assigned_node_id,
            fencing_token=seq,
            capability_scope=capability_scope,
            issued_at=now,
            expires_at=now + ttl
        )
        self.leases[task_id] = lease
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
