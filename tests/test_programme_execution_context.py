"""Planning needs actual tool prerequisites before inventing an executable job."""
import json
from types import SimpleNamespace

from backend.runtime.work_programmes import WorkProgrammes
from test_project_test_missions import runtime


def test_context_reports_granted_tools_and_missing_controller_dependencies(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda name: None)
    service = object.__new__(WorkProgrammes)
    service.engine = SimpleNamespace(
        swarm=SimpleNamespace(registry=SimpleNamespace(_knights={'coder': {}, 'researcher': {}})),
        security=SimpleNamespace(nodes=SimpleNamespace(get_node_capabilities=lambda role:
            {'filesystem.read', 'filesystem.write'} if role == 'coder' else {'filesystem.read'})))
    result = json.loads(service._execution_context())
    assert not result['controller_environment']['node_available']
    assert not result['controller_environment']['git_available']
    coder, reader = result['workers']
    assert coder['role'] == 'coder'
    assert 'workspace.write@1.0.0' in coder['tools']
    assert 'workspace.write@1.0.0' not in reader['tools']
    assert 'process.run@1.0.0' not in coder['tools']
    assert 'Not worker acknowledgement' in result['scope']


def test_context_does_not_confuse_available_node_with_process_authority(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda name: '/installed/' + name)
    service = object.__new__(WorkProgrammes)
    service.engine = SimpleNamespace(
        swarm=SimpleNamespace(registry=SimpleNamespace(_knights={'coder': {}})),
        security=SimpleNamespace(nodes=SimpleNamespace(get_node_capabilities=lambda role: set())))
    result = json.loads(service._execution_context())
    assert result['controller_environment']['node_available']
    assert result['workers'][0]['tools'] == []


def test_missing_inventory_is_unknown_and_never_invents_a_worker():
    service = object.__new__(WorkProgrammes)
    service.engine = SimpleNamespace()
    result = json.loads(service._execution_context())
    assert result['worker_inventory_available'] is False
    assert result['workers'] == []


def test_function_planner_is_told_the_required_case_profile_contract(runtime):
    import asyncio
    from unittest.mock import AsyncMock
    engine,backlog,_=runtime
    engine.models=SimpleNamespace(plan_chat=AsyncMock(return_value={'text':'{"question":"Which source?"}'}))
    service=WorkProgrammes(backlog.db,engine,backlog)
    state=service.create('kingdom','function-contract','- Check bounded function',planner_mode='configured_chat')
    asyncio.run(service.plan_next(state['id'],state['revision']))
    prompt=engine.models.plan_chat.await_args.args[0]
    assert 'case_profile' in prompt and 'bounded_batch_size.v1' in prompt
    assert 'repair_source' in prompt and 'input_from' in prompt

