import io
import json
import sys
import zipfile
from types import SimpleNamespace

import pytest

from backend.storage.db import Database
from backend.runtime.attachments import AttachmentStore, compact_text
from backend.runtime.computer_tools import workspace_path, write_file, read_file, run_process, package_workspace
from backend.runtime.missions import MissionPlan, MissionService, validate_plan
from backend.runtime.policy import ExecutionPolicy
from backend.models.profiles import ModelProfiles


@pytest.fixture
def database(tmp_path):
    return Database(tmp_path/'test.db')


def test_attachment_compression_dedup_and_integrity(database,tmp_path):
    store=AttachmentStore(database,tmp_path/'attachments')
    raw=('A useful source document.\n'*1000).encode()
    first=store.put('notes.txt',raw)
    assert first['stored_bytes']<first['bytes']
    assert store.put('same.txt',raw)['id']==first['id']
    assert store.raw(first['id'])==raw
    assert store.get(first['id'],True)['text']==raw.decode()
    (store.root/first['id']).write_bytes(b'corrupt')
    with pytest.raises(Exception): store.raw(first['id'])


@pytest.mark.parametrize('name',['../escape.py','/absolute.py','C:/escape.py','safe/../../escape.py'])
def test_zip_paths_rejected(database,tmp_path,name):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive: archive.writestr(name,'print(1)')
    with pytest.raises(ValueError): AttachmentStore(database,tmp_path/'inputs').put('project.zip',output.getvalue())
    assert not (tmp_path/'escape.py').exists()


def test_zip_inspects_code_without_executing(database,tmp_path):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive: archive.writestr('src/main.py','raise RuntimeError("must not run")')
    store=AttachmentStore(database,tmp_path/'inputs')
    item=store.put('project.zip',output.getvalue())
    assert 'raise RuntimeError' in store.get(item['id'],True)['text']
    assert len(item['members'])==1


def test_image_and_blank_pdf_are_honest(database,tmp_path):
    from PIL import Image
    from pypdf import PdfWriter
    store=AttachmentStore(database,tmp_path/'inputs')
    output=io.BytesIO();Image.new('RGB',(12,15)).save(output,format='JPEG')
    item=store.put('photo.jpg',output.getvalue())
    assert (item['width'],item['height'])==(12,15)
    assert 'requires a vision-capable model' in store.get(item['id'],True)['text']
    output=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(output)
    item=store.put('blank.pdf',output.getvalue())
    assert not item['text_extracted'] and not item['ocr_performed']


def test_compaction_preserves_relevant_source_offsets():
    source=('ordinary filler '*5000)+' distinctive_requirement details'
    result=compact_text(source,'distinctive_requirement',4000)
    assert result['compacted'] and len(result['text'])<=4000
    assert 'distinctive_requirement' in result['text'] and '[source characters ' in result['text']


def test_model_secret_is_encrypted_and_write_only(database,tmp_path):
    profiles=ModelProfiles(database,tmp_path/'secrets')
    config={'endpoint':'https://example.com/v1','model':'custom','provider':'openai_compatible','variant':'fine_tuned'}
    profiles.save('coder',config,'synthetic-test-secret')
    assert 'synthetic-test-secret' not in json.dumps(profiles.list())
    assert profiles.get('coder')['has_credentials']
    with database.get_connection() as connection:
        assert b'synthetic-test-secret' not in connection.execute('SELECT secret FROM model_profiles').fetchone()[0]
    profiles.save('coder',config)
    assert profiles.get('coder',True)['api_key']=='synthetic-test-secret'
    profiles.save('coder',config,'')
    assert not profiles.get('coder')['has_credentials']
    with pytest.raises(ValueError): profiles.save('coder',{**config,'endpoint':'http://remote.example/v1'})


@pytest.mark.parametrize('name',['../escape','C:/escape','/escape'])
def test_workspace_escape_rejected(monkeypatch,tmp_path,name):
    monkeypatch.setenv('KINGDOM_WORKSPACE',str(tmp_path/'workspace'))
    with pytest.raises(ValueError): workspace_path(name)


def test_real_write_read_package_and_command(monkeypatch,tmp_path):
    monkeypatch.setenv('KINGDOM_WORKSPACE',str(tmp_path/'workspace'))
    write_file({'path':'project/main.py','content':'print("hello")\n'})
    assert read_file({'path':'project/main.py'})['text']=='print("hello")\n'
    result=run_process({'argv':[sys.executable,'project/main.py']})
    assert result['exit_code']==0 and result['output'].strip()=='hello'
    package=package_workspace({'path':'project','_receipt_id':'test-receipt'})
    with zipfile.ZipFile(workspace_path(package['path'])) as archive:
        assert archive.namelist()==['main.py']
    result=run_process({'argv':[sys.executable,'-c','raise SystemExit(3)']})
    assert result['exit_code']==3


def test_process_has_time_and_output_limits(monkeypatch,tmp_path):
    monkeypatch.setenv('KINGDOM_WORKSPACE',str(tmp_path/'workspace'))
    with pytest.raises(TimeoutError):
        run_process({'argv':[sys.executable,'-c','import time;time.sleep(5)'],'timeout_seconds':1})
    with pytest.raises(TimeoutError):
        run_process({'argv':[sys.executable,'-c','import sys,time;sys.stdout.write("x"*3000000);sys.stdout.flush();time.sleep(5)']})


def plan():
    return MissionPlan(title='Project',objective='Build a tested utility',deliverables=['working source'],steps=[
        {'id':'check','title':'Check source','kind':'text_check','instructions':'test data','acceptance':'Measured source text'}])


def test_mission_revisions_invalidate_approval_and_missing_requirements_block(database):
    engine=SimpleNamespace(execution_policy=ExecutionPolicy(database),events=SimpleNamespace(publish=lambda *args:None))
    service=MissionService(engine,database)
    state=service.create(plan());service.approve(state['id'],1)
    with pytest.raises(ValueError): service.revise(state['id'],plan(),1)
    state=service.create(plan());state=service.revise(state['id'],plan(),1)
    with pytest.raises(ValueError): service.approve(state['id'],1)
    assert service.approve(state['id'],2)['approved_version']==2
    blocked=plan();blocked.missing_requirements=['Provider credentials']
    state=service.create(blocked)
    with pytest.raises(ValueError): service.approve(state['id'],1)


def test_mission_dag_rejects_unreviewed_bindings():
    candidate=plan();candidate.steps[0].input_from='future'
    with pytest.raises(ValueError): validate_plan(candidate)


@pytest.mark.parametrize('verification,exit_code',[('UNVERIFIED',0),('VERIFIED',2)])
def test_mission_cannot_complete_without_successful_verified_evidence(database,verification,exit_code):
    task={'id':'task','status':'completed','result':{'results':[{'verification':{'state':verification},'outcome':{'output':{'exit_code':exit_code}}}]}}
    engine=SimpleNamespace(execution_policy=ExecutionPolicy(database),events=SimpleNamespace(publish=lambda *args:None),tasks=SimpleNamespace(get=lambda ident:task))
    service=MissionService(engine,database);state=service.create(plan());service.approve(state['id'],1)
    state=service.get(state['id']);state['steps']={'check':{'task_id':'task'}};service.save(state)
    assert service.advance(state['id'])['status']=='needs_review'


def test_five_levels_have_meaningful_mission_budgets(database):
    policy=ExecutionPolicy(database)
    for level in range(1,6): assert policy.set(level)['level']==level
    assert policy.mission_budget(4)['auto_advance']
    assert not policy.mission_budget(3)['auto_advance']
    assert policy.mission_budget(5)['max_steps']>policy.mission_budget(4)['max_steps']
    assert policy.mission_budget(5)['cross_computer'] and not policy.mission_budget(4)['cross_computer']


def test_repair_scope_must_be_explicit_and_reviewed():
    candidate=plan();candidate.steps[0].repair_source='check'
    with pytest.raises(ValueError):validate_plan(candidate)


def test_repair_retains_failed_evidence_and_keeps_command_fixed(database,monkeypatch,tmp_path):
    from backend.runtime.tasks import TaskManager
    from backend.storage.repository import TaskRepository
    monkeypatch.setenv('KINGDOM_WORKSPACE',str(tmp_path/'workspace'))
    tasks=TaskManager(TaskRepository(database))
    def finish(ident,result):
        assert tasks.claim_next()['id']==ident
        tasks.complete(ident,result)
    engine=SimpleNamespace(execution_policy=ExecutionPolicy(database),events=SimpleNamespace(publish=lambda *args:None),tasks=tasks,
                           submit_task=lambda prompt,meta:tasks.create(prompt,meta))
    engine.execution_policy.set(4)
    service=MissionService(engine,database)
    candidate=MissionPlan(title='Repair utility',objective='Correct addition',deliverables=['tested utility'],steps=[
        {'id':'source','title':'Write implementation','kind':'write_file','path':'app.py','instructions':'def add(a,b): return a-b','acceptance':'Source recorded'},
        {'id':'test','title':'Run fixed tests','kind':'command','argv':['python','fixed_tests.py'],'depends_on':['source'],'repair_source':'source','acceptance':'Unchanged tests pass'}])
    state=service.create(candidate);service.approve(state['id'],1)
    written=write_file({'path':'app.py','content':'def add(a,b): return a-b'})
    source=tasks.create('source',{});finish(source['id'],{'results':[{'verification':{'state':'VERIFIED'},'outcome':{'output':written}}]})
    failed=tasks.create('tests',{});finish(failed['id'],{'results':[{'verification':{'state':'VERIFIED'},'outcome':{'output':{'exit_code':1,'output':'assert 2 + 3 == 5 failed'}}}]})
    state=service.get(state['id']);state['steps']={'source':{'task_id':source['id']},'test':{'task_id':failed['id']}};service.save(state)
    state=service.advance(state['id']);diagnose=state['repair']['task_id']
    assert state['repair_history'][0]['failed_task_id']==failed['id']
    fixed='def add(a,b): return a+b'
    finish(diagnose,{'results':[{'verification':{'state':'VERIFIED'},'outcome':{'output':{'text':fixed}}}]})
    state=service.advance(state['id']);write_id=state['repair']['task_id']
    assert tasks.get(write_id)['metadata']['tool_parameters']=={'path':'app.py','content':fixed}
    written=write_file(tasks.get(write_id)['metadata']['tool_parameters'])
    finish(write_id,{'results':[{'verification':{'state':'VERIFIED'},'outcome':{'output':written}}]})
    state=service.advance(state['id']);retest=state['repair']['task_id']
    assert tasks.get(retest)['metadata']['tool_parameters']['argv']==['python','fixed_tests.py']
    finish(retest,{'results':[{'verification':{'state':'VERIFIED'},'outcome':{'output':{'exit_code':0}}}]})
    service.advance(state['id'])
    assert service.advance(state['id'])['status']=='completed'
    assert tasks.get(failed['id'])['result']['results'][0]['outcome']['output']['exit_code']==1


def test_offload_requires_fresh_approved_capacity():
    from backend.cluster.hierarchy import offload_candidate
    from backend.cluster.node_registry import NodeInfo
    import time
    node=NodeInfo('laptop-two',fingerprint='fingerprint',public_identity={'node_id':'laptop-two'},granted_capabilities=['compute'],
                  connection_metadata={'load_metrics':{'cpu_percent':12,'memory_percent':40}})
    registry=SimpleNamespace(list_nodes=lambda:[node])
    assert offload_candidate(registry,'compute')=='laptop-two'
    node.last_heartbeat=time.time()-60
    assert offload_candidate(registry,'compute') is None
    node.last_heartbeat=time.time();node.connection_metadata={}
    assert offload_candidate(registry,'compute') is None
    node.connection_metadata={'load_metrics':{'cpu_percent':12,'memory_percent':40}};node.node_state_val='REVOKED'
    assert offload_candidate(registry,'compute') is None


def test_captain_authority_stays_in_its_group(database):
    from backend.cluster.hierarchy import CommandHierarchy
    from backend.cluster.node_registry import NodeInfo
    nodes=[NodeInfo(name,fingerprint=name,public_identity={'node_id':name}) for name in ('captain','member','outsider')]
    hierarchy=CommandHierarchy(database,SimpleNamespace(list_nodes=lambda:nodes),lambda *args:None)
    group=hierarchy.create_group('Team','captain',['captain','member'])
    assert hierarchy.authorize_assignment('captain',group['id'],'member')['id']==group['id']
    with pytest.raises(PermissionError): hierarchy.authorize_assignment('outsider',group['id'],'member')
    with pytest.raises(PermissionError): hierarchy.authorize_assignment('captain',group['id'],'outsider')
    nodes[0].node_state_val='REVOKED'
    with pytest.raises(PermissionError): hierarchy.authorize_assignment('captain',group['id'],'member')
