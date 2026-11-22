"""Integration contracts for non-interfering browser tasks (no live internet needed)."""
import hashlib
from pathlib import Path

import pytest

from backend.runtime.agent_sessions import BrowserPlanArgs, TOOLS
from backend.runtime.computer_tools import TOOL_CAPABILITIES, receipt, verify_receipt
from backend.runtime.execution import native_tools


TOOL = 'computer.browser.run@1.0.0'


def test_browser_agent_tool_is_registered_and_schema_rejects_unknown_fields():
    assert TOOLS['browser_run'][0] == TOOL
    validated = BrowserPlanArgs.model_validate({
        'start_url': 'https://example.org', 'allowed_hosts': ['example.org'],
        'actions': [],
    })
    assert validated.start_url == 'https://example.org'
    with pytest.raises(Exception):
        BrowserPlanArgs.model_validate({
            'start_url': 'https://example.org', 'allowed_hosts': ['example.org'],
            'actions': [], 'unsafe_javascript': 'alert(1)',
        })


def test_browser_requires_existing_computer_and_network_capabilities():
    tools = native_tools()
    assert TOOL_CAPABILITIES[TOOL] == 'computer.control'
    assert set(tools._tools[TOOL].required_capabilities) == {
        'computer.control', 'network.access'
    }
    assert tools._tools[TOOL].idempotent is False
    params = {'start_url': 'https://example.org', 'allowed_hosts': ['example.org'],
              'actions': [], '_receipt_id': 'job'}
    assert 'Missing required capability: network.access' in tools.validate_tool_invocation(
        TOOL, params, ['computer.control'], [])
    assert 'Missing required capability: computer.control' in tools.validate_tool_invocation(
        TOOL, params, ['network.access'], [])


def test_verified_receipt_rejects_modified_headless_capture(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    capture = Path('data/browser-captures/fake.png')
    capture.parent.mkdir(parents=True)
    capture.write_bytes(b'original-screenshot')
    output = {
        'capture': str(capture),
        'capture_sha256': hashlib.sha256(capture.read_bytes()).hexdigest(),
    }
    task = {'id': 'test-task', 'metadata': {'tool': TOOL}}
    result = {'output': output, **receipt(task, output)}
    assert verify_receipt(task, result)['state'] == 'VERIFIED'
    capture.write_bytes(b'tampered-screenshot')
    with pytest.raises(ValueError, match='Headless browser capture'):
        verify_receipt(task, result)


@pytest.fixture
def runtime(tmp_path):
    from backend.runtime.engine import RuntimeEngine
    from backend.runtime.tasks import TaskManager
    from backend.storage.db import Database
    from backend.storage.repository import TaskRepository
    instance = RuntimeEngine()
    instance.tasks = TaskManager(TaskRepository(Database(tmp_path / 'browser-runtime.db')))
    return instance


def test_browser_submission_is_one_attempt_even_if_caller_requests_retries(runtime):
    task = runtime.submit_task('experimental browser', {
        'actor': 'owner', 'tool': TOOL, 'max_attempts': 5,
        'tool_parameters': {
            'start_url': 'https://example.org',
            'allowed_hosts': ['example.org'], 'actions': [],
        },
    })
    assert task['max_attempts'] == 1
    assert task['metadata']['max_attempts'] == 1
    assert task['metadata']['capability'] == 'computer.control'


@pytest.mark.parametrize('remote', [
    {'offload': True}, {'execution_target': 'remote'},
])
def test_experimental_browser_does_not_auto_offload_to_unverified_peer(runtime, remote):
    with pytest.raises(ValueError, match='local-only'):
        runtime.submit_task('experimental browser', {
            'actor': 'owner', 'tool': TOOL,
            'tool_parameters': {
                'start_url': 'https://example.org',
                'allowed_hosts': ['example.org'], 'actions': [],
            },
            **remote,
        })



def test_browser_network_permission_is_explicit_revocable_and_never_standalone(runtime):
    from backend.runtime.workspace_api import ComputerGrant
    role = next(iter(runtime.swarm.registry._knights))
    with pytest.raises(ValueError, match='requires a separate computer-control grant'):
        runtime.grant_computer_tools(role, ['network.access'], persist=False)
    selected = ComputerGrant.model_validate({
        'capabilities': ['computer.control', 'network.access'],
    })
    saved = runtime.grant_computer_tools(role, selected.capabilities, persist=False)
    assert set(saved['capabilities']) == {'computer.control', 'network.access'}
    assert {'computer.control', 'network.access'} <= set(
        runtime.security.nodes.get_node_capabilities(role))
    assert {'computer.control', 'network.access'} <= set(
        runtime.swarm.registry.get(role).zero_trust.nodes.get_node_capabilities(role))
    # Removing the network grant must revoke it from both execution boundaries.
    runtime.grant_computer_tools(role, ['computer.control'], persist=False)
    assert 'network.access' not in runtime.security.nodes.get_node_capabilities(role)
    assert 'network.access' not in runtime.swarm.registry.get(role).zero_trust.nodes.get_node_capabilities(role)
