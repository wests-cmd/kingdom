import os
import subprocess
import sys
from pathlib import Path
import pytest
from backend.runtime.workflow_engine import CheckpointManager, WorkflowContract, AutonomyLevel
from backend.storage.db import Database


def test_workflow_snapshot_survives_separate_process_and_preserves_budget(tmp_path):
    path = tmp_path/'checkpoint.sqlite3'
    script = '''
import sys
from backend.storage.db import Database
from backend.runtime.workflow_engine import CheckpointManager,WorkflowContract,AutonomyLevel
contract=WorkflowContract(workflow_id='durable',actor_identity_id='owner',objective='review',autonomy_level=AutonomyLevel.LEVEL_2_APPROVED_WORKFLOWS)
contract.completed_steps.append({'id':'first','verified':True})
contract.budget.consume_step(cost_usd=0.5,is_tool_call=True)
CheckpointManager(Database(sys.argv[1])).save_checkpoint(contract)
'''
    repo = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=str(repo))
    result = subprocess.run([sys.executable,'-c',script,str(path)],cwd=tmp_path,env=environment,capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stderr
    manager = CheckpointManager(Database(path))
    restored = manager.load_checkpoint('durable')
    assert isinstance(restored,WorkflowContract)
    assert restored.actor_identity_id == 'owner'
    assert restored.autonomy_level == AutonomyLevel.LEVEL_2_APPROVED_WORKFLOWS
    assert restored.budget.used_steps == 1 and restored.budget.used_tool_calls == 1
    assert restored.budget.used_cost_usd == 0.5
    assert restored.completed_steps == [{'id':'first','verified':True}]
    restored.completed_steps.clear()
    assert len(manager.load_checkpoint('durable').completed_steps) == 1
    assert restored.state.value == 'PENDING'


def test_plain_state_is_durable_and_invalid_save_keeps_previous_checkpoint(tmp_path):
    database = Database(tmp_path/'checkpoint.sqlite3')
    manager = CheckpointManager(database)
    state = {'processed':['first']}
    manager.save_checkpoint('task',step_index=1,state=state)
    state['processed'].append('later')
    restarted = CheckpointManager(database)
    assert restarted.load_checkpoint('task')['state'] == {'processed':['first']}
    for index, invalid in [(-1,{}),(2,{'metric':float('nan')}),(2,{'invalid':object()})]:
        with pytest.raises((ValueError,TypeError)):
            manager.save_checkpoint('task',step_index=index,state=invalid)
    assert restarted.load_checkpoint('task')['step_index'] == 1
    assert restarted.load_checkpoint('absent') is None
    corrupted = manager.repository.get('workflow_checkpoint','task')
    corrupted['format_version'] = 999
    manager.repository.put('workflow_checkpoint','task',corrupted)
    with pytest.raises(ValueError):
        restarted.load_checkpoint('task')
