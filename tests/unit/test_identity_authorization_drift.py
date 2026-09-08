import os
import time
import pytest
from backend.security.identity_fabric import IdentityFabric, IdentityType, IdentityState
from backend.security.scoped_authorization import ScopedAuthorizationEngine, AuthorizationRequest
from backend.security.plan_drift import PlanDriftEngine
from backend.security.verification_engine import IndependentVerificationEngine, VerificationState


def test_identity_fabric_lifecycle():
    fabric = IdentityFabric()

    # 1. Register identity
    ident = fabric.register_identity(
        identity_type=IdentityType.KNIGHT,
        display_name="Knight Executor Alpha",
        capabilities=["filesystem.read", "filesystem.write"]
    )
    assert ident.state == IdentityState.AUTHENTICATED

    # 2. Activate identity
    fabric.activate_identity(ident.identity_id)
    assert fabric.get_identity(ident.identity_id).state == IdentityState.ACTIVE

    # 3. Suspend identity
    fabric.suspend_identity(ident.identity_id, reason="Security review")
    with pytest.raises(PermissionError, match="is not ACTIVE"):
        fabric.verify_active_identity(ident.identity_id)

    # 4. Activate then Revoke identity
    fabric.activate_identity(ident.identity_id)
    fabric.revoke_identity(ident.identity_id, reason="Compromised credentials")
    assert fabric.get_identity(ident.identity_id).state == IdentityState.REVOKED

    # Terminal state cannot be re-activated
    with pytest.raises(ValueError, match="is in terminal state"):
        fabric.activate_identity(ident.identity_id)


def test_scoped_authorization_and_data_scope():
    fabric = IdentityFabric()
    ident = fabric.register_identity(
        identity_type=IdentityType.SKILL,
        display_name="Data Mining Skill",
        capabilities=["data.read"]
    )
    fabric.activate_identity(ident.identity_id)

    auth_engine = ScopedAuthorizationEngine(fabric)

    # 1. Valid authorization
    req = AuthorizationRequest(
        actor_identity_id=ident.identity_id,
        capability="data.read",
        operation="query",
        resource="sales_db"
    )
    decision = auth_engine.evaluate_authorization(req)
    assert decision.allowed is True

    # 2. Missing capability grant
    req_missing = AuthorizationRequest(
        actor_identity_id=ident.identity_id,
        capability="filesystem.delete",
        operation="delete",
        resource="/root/config"
    )
    dec_missing = auth_engine.evaluate_authorization(req_missing)
    assert dec_missing.allowed is False
    assert "lacks required capability" in dec_missing.reason

    # 3. Data scope restriction (UNVERIFIED identity attempting restricted scope)
    req_scope = AuthorizationRequest(
        actor_identity_id=ident.identity_id,
        capability="data.read",
        operation="query",
        resource="payroll_db",
        data_scope="finance",
        context={"restricted_data_scopes": ["finance"]}
    )
    dec_scope = auth_engine.evaluate_authorization(req_scope)
    assert dec_scope.allowed is False
    assert "restricted to TRUSTED" in dec_scope.reason


def test_plan_drift_engine():
    drift_engine = PlanDriftEngine()

    # 1. Bind approved plan
    binding = drift_engine.bind_approved_plan(
        plan_id="plan_123",
        actor_identity_id="id_knight_1",
        tool_id="tool_file_writer",
        operation="write",
        resource="/data/output.txt",
        params={"content": "Hello Kingdom"},
        risk_level="MEDIUM"
    )
    assert binding.plan_id == "plan_123"

    # 2. Valid execution
    valid = drift_engine.validate_plan_execution(
        plan_id="plan_123",
        actor_identity_id="id_knight_1",
        tool_id="tool_file_writer",
        operation="write",
        resource="/data/output.txt",
        params={"content": "Hello Kingdom"}
    )
    assert valid is True

    # 3. Parameter Drift Attack
    with pytest.raises(PermissionError, match="Parameter drift detected"):
        drift_engine.validate_plan_execution(
            plan_id="plan_123",
            actor_identity_id="id_knight_1",
            tool_id="tool_file_writer",
            operation="write",
            resource="/data/output.txt",
            params={"content": "MALICIOUS OVERWRITE"}
        )

    # 4. Tool Substitution Attack on new plan
    drift_engine.bind_approved_plan(
        plan_id="plan_456",
        actor_identity_id="id_knight_1",
        tool_id="tool_read",
        operation="read",
        resource="/data/input.txt",
        params={}
    )
    with pytest.raises(PermissionError, match="Plan scope drift detected"):
        drift_engine.validate_plan_execution(
            plan_id="plan_456",
            actor_identity_id="id_knight_1",
            tool_id="tool_system_exec",  # Substituted tool!
            operation="read",
            resource="/data/input.txt",
            params={}
        )


def test_independent_verification_engine(tmp_path):
    # 1. Filesystem write verification - Success
    file_path = str(tmp_path / "verified_test.txt")
    with open(file_path, "w") as f:
        f.write("Verified content")

    res_success = IndependentVerificationEngine.verify_filesystem_write(file_path, expected_min_bytes=5)
    assert res_success.observed_state == VerificationState.VERIFIED

    # 2. Filesystem write verification - Failure (non-existent file)
    res_fail = IndependentVerificationEngine.verify_filesystem_write("/non/existent/file.txt")
    assert res_fail.observed_state == VerificationState.FAILED

    # 3. External action verification - UNKNOWN state when verifier absent
    res_unknown = IndependentVerificationEngine.verify_external_action(
        target_resource="https://api.external.com/send",
        claimed_success=True,
        verifier_callback=None
    )
    assert res_unknown.observed_state == VerificationState.UNKNOWN
