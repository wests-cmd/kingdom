"""Private-browser screenshots are owner-only, hash-checked and confined."""
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.api import engine
from backend.runtime.computer_tools import receipt, workspace_path
from tests.auth_support import owner_client


def prepare_task(tmp_path, monkeypatch, *, outside=False):
    monkeypatch.chdir(tmp_path)
    prompt = 'Private browser inspection'
    parent = 'private-screenshot-task'
    execution_id = parent + ':' + hashlib.sha256(prompt.encode()).hexdigest()
    directory = workspace_path('browser-captures')
    directory.mkdir(parents=True, exist_ok=True)
    capture = (tmp_path / 'unapproved.png') if outside else (directory / 'expected.png')
    capture.write_bytes(b'\x89PNG\r\n\x1a\nprivate-evidence')
    output = {
        'capture': str(capture),
        'capture_sha256': hashlib.sha256(capture.read_bytes()).hexdigest(),
        'url': 'https://example.org/',
        'text': 'test-private-preview',
    }
    execution_task = {'id': execution_id, 'metadata': {'tool': 'computer.browser.run@1.0.0'}}
    artifact = receipt(execution_task, output)
    task = {
        'id': parent, 'status': 'completed', 'prompt': prompt,
        'metadata': {'tool': 'computer.browser.run@1.0.0'},
        'result': {'results': [{'outcome': {
            'kind': 'native_tool', 'tool': 'computer.browser.run@1.0.0',
            'output': output, **artifact,
        }}]},
    }
    monkeypatch.setattr(engine.tasks, 'get', lambda ident: task if ident == parent else None)
    return capture, parent


def test_private_browser_capture_requires_owner_even_when_task_exists(tmp_path, monkeypatch):
    capture, ident = prepare_task(tmp_path, monkeypatch)
    anonymous = TestClient(app).get(f'/workspace/tasks/{ident}/artifact')
    assert anonymous.status_code == 401
    authorized = owner_client(app).get(f'/workspace/tasks/{ident}/artifact')
    assert authorized.status_code == 200
    assert authorized.content == capture.read_bytes()
    assert authorized.headers['content-type'].startswith('image/png')


def test_private_browser_capture_fails_when_changed(tmp_path, monkeypatch):
    capture, ident = prepare_task(tmp_path, monkeypatch)
    capture.write_bytes(b'\x89PNG\r\n\x1a\nmodified')
    response = owner_client(app).get(f'/workspace/tasks/{ident}/artifact')
    assert response.status_code == 409
    assert response.content != capture.read_bytes()


def test_private_browser_capture_fails_when_output_points_outside_workspace(tmp_path, monkeypatch):
    capture, ident = prepare_task(tmp_path, monkeypatch, outside=True)
    response = owner_client(app).get(f'/workspace/tasks/{ident}/artifact')
    assert response.status_code == 409
    assert response.content != capture.read_bytes()
