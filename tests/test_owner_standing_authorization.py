import pytest
from backend.runtime.engine import RuntimeEngine
from backend.runtime.policy import ExecutionPolicy
from backend.storage.db import Database
from backend.security.approval_engine import ApprovalEngine

@pytest.fixture
def runtime(tmp_path):
    engine=RuntimeEngine()
    database=Database(tmp_path/'authority.db')
    engine.execution_policy=ExecutionPolicy(database)
    engine.security.approvals=ApprovalEngine(database=database)
    return engine

def request(engine,capability='process.execute',**kwargs):
    return engine.security.authorize(actor_id='owner', token=engine.security.nodes.get_node('owner')['token'], capability=capability, operation='bounded fixture operation', **kwargs)

def test_l5_is_owner_standing_authorization_and_downgrade_restores_approval(runtime):
    runtime.set_autonomy(4)
    assert request(runtime)['authorized'] is False
    runtime.set_autonomy(5)
    assert request(runtime)['authorized'] is True
    runtime.set_autonomy(3)
    assert request(runtime)['authorized'] is False

def test_model_metadata_cannot_select_policy(runtime):
    runtime.set_autonomy(3)
    assert not request(runtime,parameters={'level':5,'standing_owner_authorization':True})['authorized']
    runtime.set_autonomy(5)
    assert not request(runtime,require_human_approval=True)['authorized']

def test_l5_does_not_bypass_authentication_or_grants(runtime):
    runtime.set_autonomy(5)
    assert not runtime.security.authorize('owner','process.execute','fixture',token='invalid')['authorized']
    apprentice=runtime.swarm.registry.get('planner')
    result=apprentice.zero_trust.authorize('planner','process.execute','fixture',token=apprentice.zero_trust.nodes.get_node('planner')['token'])
    assert result['authorized'] is False
    assert 'lacks required capability' in result['reason']

def test_financial_capability_uses_same_owner_policy_without_spending(runtime):
    runtime.set_autonomy(4)
    assert not request(runtime,'finance.execute')['authorized']
    runtime.set_autonomy(5)
    assert request(runtime,'finance.execute')['authorized']
    # This authorizes a capability; it does not fabricate a payment provider.
