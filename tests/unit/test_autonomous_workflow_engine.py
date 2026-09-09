import pytest
from backend.runtime.workflow_engine import (
    WorkflowContract,
    WorkflowResourceBudget,
    WorkflowState,
    AutonomyLevel,
    CheckpointManager,
    CompensationEngine,
    EmergencyIncidentMode,
)


def test_workflow_resource_budget_enforcement():
    budget = WorkflowResourceBudget(max_steps=2, max_cost_usd=1.0)

    # Step 1
    budget.consume_step(cost_usd=0.5)
    assert budget.used_steps == 1

    # Step 2
    budget.consume_step(cost_usd=0.4)
    assert budget.used_steps == 2

    # Step 3 breaches max_steps
    with pytest.raises(RuntimeError, match="Max steps"):
        budget.consume_step(cost_usd=0.1)


def test_checkpoint_manager_restoration():
    mgr = CheckpointManager()
    contract = WorkflowContract(
        actor_identity_id="id_analyst",
        objective="Analyze quarterly earnings",
        autonomy_level=AutonomyLevel.LEVEL_2_APPROVED_WORKFLOWS
    )

    contract.completed_steps.append({"step_id": "step_1", "status": "ok"})
    mgr.save_checkpoint(contract)

    # Modify original contract after checkpointing
    contract.completed_steps.append({"step_id": "step_2", "status": "ok"})

    # Loaded checkpoint preserves original step 1 state
    restored = mgr.load_checkpoint(contract.workflow_id)
    assert restored is not None
    assert len(restored.completed_steps) == 1
    assert restored.completed_steps[0]["step_id"] == "step_1"


def test_compensation_engine():
    engine = CompensationEngine()
    executed_params = []

    def email_compensator(params):
        executed_params.append(params)
        return True

    engine.register_compensator("send_cancellation_email", email_compensator)

    action = {
        "action_type": "send_cancellation_email",
        "params": {"to": "customer@kingdom.org", "reason": "Order cancelled"}
    }

    res = engine.execute_compensation(action)
    assert res is True
    assert len(executed_params) == 1
    assert executed_params[0]["to"] == "customer@kingdom.org"


def test_emergency_incident_mode():
    incident_mode = EmergencyIncidentMode()
    assert incident_mode.active is False

    # Normal execution check passes
    incident_mode.enforce_incident_check()

    # Operator activates emergency lockdown
    incident_mode.activate_emergency_lockdown("operator_alex", "Active credential leak detected")
    assert incident_mode.active is True

    # Enforcement check raises PermissionError
    with pytest.raises(PermissionError, match="Emergency Incident Lockdown ACTIVE"):
        incident_mode.enforce_incident_check()

    # Operator deactivates lockdown
    incident_mode.deactivate_emergency_lockdown("operator_alex")
    assert incident_mode.active is False
    incident_mode.enforce_incident_check()
