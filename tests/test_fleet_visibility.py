import contextlib
import json
import sqlite3
import os
import time
import pytest
from backend.runtime.fleet_activity import local_activity, validate_activity
from backend.cluster.apprentice_inventory import aggregate_inventories
from backend.runtime import service_discovery as services


def host_report():
    return {'version':1, 'state':'observed', 'observed_at':time.time(),
            'containers':[{'name':'kingdom-workshop','state':'running','restart_policy':'unless-stopped',
                           'environment':'SECRET-MUST-NOT-PROPAGATE'}]}


def test_readonly_host_report_reaches_signed_peer_inventory(tmp_path):
    report=tmp_path/'containers.json'; report.write_text(json.dumps(host_report()));report.chmod(0o644)
    observed=services.read_host_container_report(report, owner_uid=os.getuid())
    assert observed['state']=='observed' and observed['observation_source']=='host_report'
    assert observed['services'][0]['id']=='docker:kingdom-workshop'
    assert observed['services'][0]['restart_policy']=='unless-stopped'
    assert observed['services'][0]['startup']=='unknown'
    from backend.cluster.apprentice_inventory import validate_inventory
    signed_payload=validate_inventory({'version':1,'apprentices':[],'services':observed})
    assert signed_payload['services']==observed
    assert 'SECRET-MUST-NOT-PROPAGATE' not in json.dumps(signed_payload)


@pytest.mark.parametrize('problem',['stale','future','symlink','writable','oversize','nonfinite','bad_name'])
def test_untrusted_host_report_never_claims_current_containers(tmp_path, problem):
    data=host_report();p=tmp_path/'containers.json'
    if problem=='stale':data['observed_at']-=120
    if problem=='future':data['observed_at']+=120
    if problem=='nonfinite':data['observed_at']=float('nan')
    if problem=='bad_name':data['containers'][0]['name']='token=secret'
    p.write_text(json.dumps(data));p.chmod(0o644)
    if problem=='oversize':p.write_text('x'*65537)
    if problem=='writable':p.chmod(0o666)
    if problem=='symlink':
        link=tmp_path/'linked.json';link.symlink_to(p);p=link
    result=services.read_host_container_report(p, owner_uid=os.getuid())
    assert result['state']=='unavailable' and result['services']==[]


def test_container_consumes_configured_report_without_docker_access(tmp_path,monkeypatch):
    monkeypatch.setattr(services.platform,'system',lambda:'Linux')
    monkeypatch.setattr(services,'in_container',lambda:True)
    monkeypatch.setenv('KINGDOM_HOST_CONTAINER_REPORT',str(tmp_path/'host.json'))
    expected={'state':'unavailable','scope':'container','observation_source':'host_report','services':[]}
    monkeypatch.setattr(services,'read_host_container_report',lambda path:expected)
    monkeypatch.setattr(services,'read_rows',lambda _:pytest.fail('Docker/host execution must not occur in agent container'))
    assert services.discover_local_services()==expected


def activity():
    return {'state':'observed','observed_at':100.0,'jobs':[{'id':'task-1','kind':'task','status':'running','tool':'file.read@1.0.0','worker':'peer-1','updated_at':99.0}]}


@pytest.mark.parametrize('extra', ['prompt','arguments','transcript','api_key'])
def test_peer_jobs_reject_private_payload(extra):
    value=activity();value['jobs'][0][extra]='private'
    with pytest.raises(ValueError):validate_activity(value)


@pytest.mark.parametrize('field', ['id','model','worker'])
def test_peer_jobs_reject_credential_shaped_labels(field):
    value=activity();value['jobs'][0][field]='ghp_private'
    with pytest.raises(ValueError):validate_activity(value)


def test_local_existing_db_filters_content_and_bounds(tmp_path):
    conn=sqlite3.connect(tmp_path/'work.db');conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE tasks(id TEXT,status TEXT,metadata_json TEXT,assigned_knight TEXT,updated_at REAL)')
    for i in range(25):
        conn.execute('INSERT INTO tasks VALUES(?,?,?,?,?)',(f'task-{i}','running',json.dumps({'tool':'file.read@1.0.0','prompt':'NEVER SHARE','api_key':'NEVER SHARE'}),'peer-1',float(i)))
    conn.commit()
    class Database:
        @contextlib.contextmanager
        def get_connection(self):yield conn
    value=local_activity(Database(),now=100.0)
    assert value['state']=='observed' and len(value['jobs'])==20 and value['truncated']
    assert value['jobs'][0]['id']=='task-24'
    assert 'NEVER SHARE' not in json.dumps(value)
    assert set(value['jobs'][0])=={'id','kind','status','tool','model','worker','updated_at'}
    conn.close()


@pytest.mark.parametrize('state,received,expected', [('CONNECTED',100,'current'),('CONNECTED',1,'stale'),('REVOKED',100,'revoked'),('DISCONNECTED',100,'stale')])
def test_receiver_freshness_and_revocation_gate_job_visibility(state,received,expected):
    node={'node_id':'peer','node_state':state,'last_heartbeat':100,'connection_metadata':{'apprentice_inventory':{'received_at':received,'report':{'version':1,'apprentices':[],'activity':activity()}}}}
    result=aggregate_inventories([], [node],now=101)
    assert result['reports'][0]['state']==expected
    assert len(result['remote_jobs'])==(1 if expected=='current' else 0)
    assert bool(result['reports'][0]['activity'])==(expected=='current')


def test_old_peer_without_activity_remains_unknown():
    node={'node_id':'peer','node_state':'CONNECTED','last_heartbeat':100,'connection_metadata':{'apprentice_inventory':{'received_at':100,'report':{'version':1,'apprentices':[]}}}}
    result=aggregate_inventories([], [node],now=101)
    assert result['reports'][0]['activity'] is None


def test_linux_startup_enabled_does_not_mean_running(monkeypatch):
    monkeypatch.setattr(services.platform,'system',lambda:'Linux')
    monkeypatch.setattr(services,'in_container',lambda:False)
    monkeypatch.setattr(services.shutil,'which',lambda _: '/usr/bin/systemctl')
    monkeypatch.setattr(services,'read_rows',lambda argv: [{'unit':'live.service','description':'Live'}] if 'list-units' in argv else [{'unit_file':'boot.service','state':'enabled'},{'unit_file':'live.service','state':'disabled'}])
    result=services.discover_local_services()
    rows={row['id']:row for row in result['services']}
    assert rows['boot.service']['state']=='stopped' and rows['boot.service']['startup']=='enabled'
    assert rows['live.service']['state']=='running' and rows['live.service']['startup']=='disabled'


def test_partial_startup_observation_keeps_running_unknown(monkeypatch):
    monkeypatch.setattr(services.platform,'system',lambda:'Linux')
    monkeypatch.setattr(services,'in_container',lambda:False)
    monkeypatch.setattr(services.shutil,'which',lambda _: '/usr/bin/systemctl')
    monkeypatch.setattr(services,'read_rows',lambda argv: None if 'list-units' in argv else [{'unit_file':'boot.service','state':'enabled'}])
    result=services.discover_local_services()
    assert result['services'][0]['state']=='unknown'
    assert result['running_state']=='unavailable'


def test_container_does_not_probe_host(monkeypatch):
    monkeypatch.setattr(services.platform,'system',lambda:'Linux')
    monkeypatch.setattr(services,'in_container',lambda:True)
    monkeypatch.setattr(services,'read_rows',lambda _:pytest.fail('host probe'))
    result=services.discover_local_services()
    assert result['state']=='unsupported' and result['scope']=='container'

def test_recent_change_on_old_agent_is_not_lost_to_creation_order(tmp_path):
    conn=sqlite3.connect(tmp_path/'agents.db');conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE agent_sessions(id TEXT PRIMARY KEY,state_json TEXT NOT NULL)')
    for i in range(25):
        state={'id':f'agent-{i}','status':'thinking','updated_at':1000.0 if i==0 else float(i),'selected_model':'safe-model','objective':'PRIVATE OBJECTIVE'}
        conn.execute('INSERT INTO agent_sessions VALUES(?,?)',(state['id'],json.dumps(state)))
    conn.commit()
    class Database:
        @contextlib.contextmanager
        def get_connection(self):yield conn
    value=local_activity(Database(),now=1001.0)
    assert value['state']=='observed' and value['jobs'][0]['id']=='agent-0'
    assert 'PRIVATE OBJECTIVE' not in json.dumps(value)
    conn.close()

def test_accepted_heartbeat_carries_only_validated_job_metadata_without_grants(monkeypatch):
    import copy
    from backend.cluster.node_registry import node_registry, NodeInfo
    from backend.cluster.heartbeat import HeartbeatManager
    stored=NodeInfo(node_id='peer',node_state_val='DISCONNECTED',last_heartbeat=1,granted_capabilities=['compute']).to_dict()
    monkeypatch.setattr(node_registry.repo,'get',lambda ident:copy.deepcopy(stored))
    monkeypatch.setattr(node_registry.repo,'save',lambda data:stored.update(copy.deepcopy(data)))
    monkeypatch.setattr('backend.cluster.heartbeat.time.time',lambda:100)
    report={'version':1,'apprentices':[],'activity':activity()}
    assert HeartbeatManager().ping('peer',apprentice_inventory=report)['success']
    assert stored['granted_capabilities']==['compute']
    result=aggregate_inventories([], [stored],now=101)
    assert result['remote_jobs'][0]['scoped_id']=='peer/task/task-1'
    assert result['remote_jobs'][0]['provenance']=='signed_peer_report'
