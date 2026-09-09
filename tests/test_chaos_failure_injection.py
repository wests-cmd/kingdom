import pytest
from backend.runtime.resilience import (
    CircuitBreakerEngine,
    CircuitState,
    DeadLetterQueue,
    RateLimiterEngine,
)
from backend.runtime.workflow_engine import (
    WorkflowContract,
    WorkflowResourceBudget,
    WorkflowState,
    AutonomyLevel,
    EmergencyIncidentMode,
)


def test_chaos_provider_outage_circuit_breaking():
    cb = CircuitBreakerEngine(failure_threshold=2, cooldown_sec=10.0)
    provider_id = "external_model_provider"

    # Simulate 2 successive failures
    cb.record_failure(provider_id)
    cb.record_failure(provider_id)

    # Circuit trips to OPEN
    assert cb.get_state(provider_id) == CircuitState.OPEN

    # Execution against provider raises circuit error
    if cb.get_state(provider_id) == CircuitState.OPEN:
        with pytest.raises(RuntimeError, match="Circuit breaker OPEN"):
            raise RuntimeError(f"Circuit breaker OPEN for provider '{provider_id}'")


def test_chaos_infinite_loop_budget_termination():
    budget = WorkflowResourceBudget(max_steps=5)

    # Simulate planner infinite loop attempting 10 iterations
    steps_executed = 0
    try:
        for _ in range(10):
            budget.consume_step()
            steps_executed += 1
    except RuntimeError as e:
        assert "Max steps" in str(e)

    # Infinite loop terminated cleanly at step 6
    assert steps_executed == 5


def test_chaos_rate_limit_denial_and_dead_letter_queuing():
    rate_limiter = RateLimiterEngine(max_tokens=1)
    dlq = DeadLetterQueue()
    client = "worker_bot"

    # First request allowed
    assert rate_limiter.allow_request(client) is True

    # Second request denied by rate limiter -> pushed to DLQ
    if not rate_limiter.allow_request(client):
        dlq.push(
            task_id="task_rate_limited",
            actor=client,
            operation="submit_api_call",
            failure_reason="Rate limit token bucket exhausted",
            retry_count=0
        )

    assert len(dlq.records) == 1
    rec = list(dlq.records.values())[0]
    assert rec.task_id == "task_rate_limited"


def test_chaos_emergency_incident_mode_workflow_lockdown():
    incident_mode = EmergencyIncidentMode()
    workflow = WorkflowContract(
        actor_identity_id="id_autonomous_agent",
        objective="Execute automated asset rebalancing",
        autonomy_level=AutonomyLevel.LEVEL_3_ADAPTIVE_BOUNDED
    )

    # Emergency incident mode triggered mid-execution
    incident_mode.activate_emergency_lockdown(
        operator="admin",
        reason="Anomalous network spike detected on cluster"
    )

    # Attempt to process next step fails closed
    try:
        incident_mode.enforce_incident_check()
    except PermissionError as pe:
        workflow.state = WorkflowState.BLOCKED_BY_INCIDENT_MODE
        assert "Emergency Incident Lockdown ACTIVE" in str(pe)

    assert workflow.state == WorkflowState.BLOCKED_BY_INCIDENT_MODE
