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
