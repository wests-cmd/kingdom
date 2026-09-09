import time
import hashlib
import json
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class IdempotencyManager:

    def __init__(self):
        self.cached_results: Dict[str, Dict[str, Any]] = {}

    def compute_key(self, request_key: str, params: Dict[str, Any]) -> str:
        serialized = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(f"{request_key}:{serialized}".encode("utf-8")).hexdigest()

    def get_cached_result(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        cached = self.cached_results.get(idempotency_key)
        if cached and cached.get("expires_at", 0) > time.time():
            return cached.get("result")
        return None

    def store_result(self, idempotency_key: str, result: Dict[str, Any], ttl_sec: float = 86400.0) -> None:
        self.cached_results[idempotency_key] = {
            "result": result,
            "expires_at": time.time() + ttl_sec
        }


class CircuitBreakerEngine:

    def __init__(self, failure_threshold: int = 3, cooldown_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        self.states: Dict[str, CircuitState] = {}
        self.failure_counts: Dict[str, int] = {}
        self.last_state_change: Dict[str, float] = {}

    def get_state(self, provider_id: str) -> CircuitState:
        now = time.time()
        state = self.states.get(provider_id, CircuitState.CLOSED)

        if state == CircuitState.OPEN:
            last_change = self.last_state_change.get(provider_id, 0.0)
            if now - last_change >= self.cooldown_sec:
                self.states[provider_id] = CircuitState.HALF_OPEN
                return CircuitState.HALF_OPEN

        return state

    def record_success(self, provider_id: str) -> None:
        self.failure_counts[provider_id] = 0
        self.states[provider_id] = CircuitState.CLOSED
        self.last_state_change[provider_id] = time.time()

    def record_failure(self, provider_id: str) -> None:
        count = self.failure_counts.get(provider_id, 0) + 1
        self.failure_counts[provider_id] = count

        if count >= self.failure_threshold:
            self.states[provider_id] = CircuitState.OPEN
            self.last_state_change[provider_id] = time.time()


class DeadLetterRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"dlq_{time.time_ns()}")
    task_id: str
    actor: str
    operation: str
    failure_reason: str
    retry_count: int
    failed_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeadLetterQueue:

    def __init__(self):
        self.records: Dict[str, DeadLetterRecord] = {}

    def push(
        self,
        task_id: str,
        actor: str,
        operation: str,
        failure_reason: str,
        retry_count: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DeadLetterRecord:
        rec = DeadLetterRecord(
            task_id=task_id,
            actor=actor,
            operation=operation,
            failure_reason=failure_reason,
            retry_count=retry_count,
            metadata=metadata or {}
        )
        self.records[rec.id] = rec
        return rec

    def list_records(self) -> List[DeadLetterRecord]:
        return list(self.records.values())


class ReconciliationEngine:

    @staticmethod
    def reconcile_unknown_state(
        task_id: str,
        check_callback: Optional[Callable[[], Optional[bool]]] = None
    ) -> Dict[str, Any]:
        if check_callback is None:
            return {
                "task_id": task_id,
                "reconciled_status": "REQUIRES_HUMAN_REVIEW",
                "message": "No independent reconciliation callback registered for task."
            }

        try:
            res = check_callback()
            if res is True:
                return {
                    "task_id": task_id,
                    "reconciled_status": "VERIFIED_SUCCESS",
                    "message": "Independent reconciliation verified task completion."
                }
            elif res is False:
                return {
                    "task_id": task_id,
                    "reconciled_status": "VERIFIED_FAILURE",
                    "message": "Independent reconciliation verified task failure."
                }
            else:
                return {
                    "task_id": task_id,
                    "reconciled_status": "REQUIRES_HUMAN_REVIEW",
                    "message": "Reconciliation check returned inconclusive state."
                }
        except Exception as e:
            return {
                "task_id": task_id,
                "reconciled_status": "REQUIRES_HUMAN_REVIEW",
                "message": f"Reconciliation exception: {str(e)}"
            }


class RateLimiterEngine:

    def __init__(self, max_tokens: int = 10, refill_rate_per_sec: float = 1.0):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate_per_sec
        self.buckets: Dict[str, Dict[str, float]] = {}

    def allow_request(self, client_id: str) -> bool:
        now = time.time()
        bucket = self.buckets.get(client_id)

        if not bucket:
            self.buckets[client_id] = {"tokens": self.max_tokens - 1.0, "last_refill": now}
            return True

        elapsed = now - bucket["last_refill"]
        tokens = min(self.max_tokens, bucket["tokens"] + (elapsed * self.refill_rate))
        bucket["last_refill"] = now

        if tokens >= 1.0:
            bucket["tokens"] = tokens - 1.0
            return True

        bucket["tokens"] = tokens
        return False
