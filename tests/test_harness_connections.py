import sys
from types import SimpleNamespace
import pytest
from backend.runtime.harnesses import HarnessConfig,HarnessService,run_harness
from backend.runtime.service_nodes import ServiceNode,ServiceNodes
from backend.storage.db import Database

def engine():
    return SimpleNamespace(events=SimpleNamespace(publish=lambda *a:None),submit_task=lambda prompt,metadata:{'prompt':prompt,'metadata':metadata})

def test_real_harness_output_no_shell_and_bounded_environment(tmp_path,monkeypatch):
    monkeypatch.setenv('KINGDOM_WORKSPACE',str(tmp_path))
    monkeypatch.setenv('KINGDOM_OWNER_TOKEN','must-not-leak')
    output=run_harness({'argv':[sys.executable,'-c','import os,sys;print(sys.argv[1]);print(os.environ.get("KINGDOM_OWNER_TOKEN","absent"))','hello; $(ignored)'],
        'timeout_seconds':3,'environment':{}})
    assert output['exit_code']==0
    assert 'hello; $(ignored)' in output['output'] and 'absent' in output['output']
    assert 'must-not-leak' not in output['output']

def test_profile_edits_do_not_change_queued_exact_command(tmp_path,monkeypatch):
    monkeypatch.setenv('KINGDOM_WORKSPACE',str(tmp_path/'workspace'))
    service=HarnessService(engine(),Database(tmp_path/'profiles.db'))
    service.save('python',HarnessConfig(name='Example harness',argv=[sys.executable,'-c','print("old")','{prompt}']))
    task=service.submit('python','literal input')
    service.save('python',HarnessConfig(name='Changed',argv=[sys.executable,'-c','print("new")','{prompt}']))
    assert task['metadata']['tool']=='harness.run@1.0.0'
    assert task['metadata']['actor']=='owner'
    assert task['metadata']['tool_parameters']['argv'][-2:]==['print("old")','literal input']

def test_harness_configuration_rejects_secrets_and_bad_placeholder(tmp_path):
    service=HarnessService(engine(),Database(tmp_path/'profiles.db'))
    with pytest.raises(ValueError):service.save('bad',HarnessConfig(name='bad',argv=[sys.executable,'prefix{prompt}']))
    with pytest.raises(ValueError):service.save('bad',HarnessConfig(name='bad',argv=[sys.executable,'{prompt}'],environment={'API_KEY':'secret'}))

def test_laptop_service_actions_are_allowlisted_governed_tasks(tmp_path):
    key=tmp_path/'key';key.write_text('test identity file')
    service=ServiceNodes(engine(),Database(tmp_path/'services.db'))
    service.save('node',ServiceNode(name='Node',ssh_executable=sys.executable,identity_file=str(key),destination='user@node.example',units=['example.service']))
    task=service.action('node','example.service','restart')
    assert task['metadata']['tool']=='process.run@1.0.0'
    assert task['metadata']['tool_parameters']['argv'][-1]=='systemctl --user restart example.service'
    with pytest.raises(ValueError):service.action('node','other.service','restart')
    with pytest.raises(ValueError):service.save('unsafe',ServiceNode(name='bad',ssh_executable=sys.executable,identity_file=str(key),destination='user@node.example',units=['x.service;id']))

def test_new_tools_remain_high_risk():
    from backend.runtime.execution import native_tools
    from backend.runtime.computer_tools import TOOL_CAPABILITIES
    assert TOOL_CAPABILITIES['harness.run@1.0.0']=='process.execute'
    tools=native_tools()
    assert tools is not None
