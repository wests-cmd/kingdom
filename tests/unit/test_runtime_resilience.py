import time
import pytest
from backend.runtime.resilience import (
    IdempotencyManager,
    CircuitBreakerEngine,
    CircuitState,
    DeadLetterQueue,
    ReconciliationEngine,
    RateLimiterEngine,
)


def test_idempotency_manager():
    mgr = IdempotencyManager()
    key = mgr.compute_key("req_101", {"action": "send_email", "to": "alice@kingdom.org"})

    # First lookup returns None
    assert mgr.get_cached_result(key) is None

    # Store result
    mgr.store_result(key, {"status": "sent", "msg_id": "msg_999"})

    # Subsequent lookup returns cached result
    cached = mgr.get_cached_result(key)
    assert cached is not None
    assert cached["msg_id"] == "msg_999"


def test_circuit_breaker_tripping_and_recovery():
    cb = CircuitBreakerEngine(failure_threshold=2, cooldown_sec=0.2)
    provider = "llm_external_api"

    # Initial state is CLOSED
    assert cb.get_state(provider) == CircuitState.CLOSED

    # Record 1 failure -> STILL CLOSED
    cb.record_failure(provider)
    assert cb.get_state(provider) == CircuitState.CLOSED

    # Record 2nd failure -> TRIPS OPEN
    cb.record_failure(provider)
    assert cb.get_state(provider) == CircuitState.OPEN

    # Wait for cooldown -> transitions to HALF_OPEN
    time.sleep(0.25)
    assert cb.get_state(provider) == CircuitState.HALF_OPEN

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success(provider)
    assert cb.get_state(provider) == CircuitState.CLOSED


def test_dead_letter_queue():
    dlq = DeadLetterQueue()
    rec = dlq.push(
        task_id="task_fail_1",
        actor="worker_1",
        operation="execute_sql",
        failure_reason="Syntax error near SELECT",
        retry_count=3,
        metadata={"db": "sales"}
    )
    assert rec.task_id == "task_fail_1"
    assert rec.retry_count == 3
    assert len(dlq.records) == 1


def test_reconciliation_engine():
    # 1. Reconciliation without callback returns REQUIRES_HUMAN_REVIEW
    res_no_cb = ReconciliationEngine.reconcile_unknown_state("task_unk_1")
    assert res_no_cb["reconciled_status"] == "REQUIRES_HUMAN_REVIEW"

    # 2. Reconciliation with callback returning True -> VERIFIED_SUCCESS
    res_success = ReconciliationEngine.reconcile_unknown_state(
        "task_unk_2",
        check_callback=lambda: True
    )
    assert res_success["reconciled_status"] == "VERIFIED_SUCCESS"

    # 3. Reconciliation with callback returning False -> VERIFIED_FAILURE
    res_fail = ReconciliationEngine.reconcile_unknown_state(
        "task_unk_3",
        check_callback=lambda: False
    )
    assert res_fail["reconciled_status"] == "VERIFIED_FAILURE"


def test_rate_limiter_engine():
    limiter = RateLimiterEngine(max_tokens=2, refill_rate_per_sec=1.0)
    client = "client_alpha"

    # Allow 1st and 2nd request
    assert limiter.allow_request(client) is True
    assert limiter.allow_request(client) is True

    # 3rd request without waiting is denied
    assert limiter.allow_request(client) is False
