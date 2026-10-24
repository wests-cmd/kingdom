import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess


def observer():
    path=Path(__file__).resolve().parents[1]/'scripts/observe-host-containers.py'
    spec=importlib.util.spec_from_file_location('host_observer',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_observer_exports_selected_fields_without_control_or_secrets(monkeypatch):
    module=observer();calls=[]
    def docker(argv,**options):
        calls.append(argv)
        assert argv[:2] in [['/usr/bin/docker','ps'],['/usr/bin/docker','inspect']]
        assert options['timeout']==7 and options['stdin']==subprocess.DEVNULL
        if argv[1]=='ps':return SimpleNamespace(stdout='foreign-app\nkingdom-workshop\n')
        assert argv[-1]=='kingdom-workshop'
        return SimpleNamespace(stdout=json.dumps({'name':'/kingdom-workshop','state':'running',
            'restart_policy':'unless-stopped','environment':'OWNER-TOKEN-PRIVATE'})+'\n')
    monkeypatch.setattr(module.subprocess,'run',docker)
    result=module.collect()
    assert result['state']=='observed'
    assert result['containers']==[{'name':'kingdom-workshop','state':'running','restart_policy':'unless-stopped'}]
    assert 'PRIVATE' not in json.dumps(result) and len(calls)==2


def test_observer_failure_is_not_a_successful_empty_inventory(monkeypatch):
    module=observer()
    def fail(*args,**kwargs):raise subprocess.TimeoutExpired('docker',7)
    monkeypatch.setattr(module.subprocess,'run',fail)
    assert module.collect()['state']=='unavailable'


def test_observer_publishes_complete_readable_snapshot(tmp_path):
    module=observer();target=tmp_path/'run/containers.json'
    module.publish(target,{'version':1,'containers':[]})
    assert json.loads(target.read_text())=={'version':1,'containers':[]}
    assert target.stat().st_mode & 0o777==0o644
    assert not target.with_suffix('.tmp').exists()
