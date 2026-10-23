import pytest
from backend.runtime.bounded_function_tests import check_function, validated_acceptance, TOOL

GOOD='def bounded_batch_size(requested, pending, hard_limit):\n    return max(0, min(requested, pending, hard_limit))\n'

@pytest.fixture(autouse=True)
def isolated_default_database(tmp_path,monkeypatch):
    from backend.storage.db import db
    monkeypatch.setattr(db,'db_path',tmp_path/'default.db')
    db.init_db()

def test_fixed_owner_cases_reject_bug_and_accept_bounded_batch_size():
    failed=check_function({'source':GOOD.replace('max(0, min(requested, pending, hard_limit))','requested'),'profile_id':'bounded_batch_size.v1'})
    assert failed['accepted'] is False and failed['cases_passed']<failed['cases_run']
    passed=check_function({'source':GOOD,'profile_id':'bounded_batch_size.v1'})
    assert passed['accepted'] is True and passed['cases_run']>=20
    assert passed['scope'].startswith('Finite integer Python-syntax subset')

@pytest.mark.parametrize('source',[
 'import os\n'+GOOD,GOOD.replace('max(0, min(requested, pending, hard_limit))','True'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','unknown'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','requested.__class__'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','2 ** 100000000'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','[requested]'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','min([requested])'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','min(*requested)'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','min(a=requested)'),
 GOOD.replace('requested, pending, hard_limit','requested=True, pending=1, hard_limit=2'),
 GOOD.replace('requested, pending, hard_limit','requested: int, pending, hard_limit'),
 '@property\n'+GOOD,GOOD.replace('    return','    def nested(): return 1\n    return'),
 GOOD.replace('    return','    while True: pass\n    return'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','2147483647 + 1'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','min'),
 GOOD.replace('    return','    requested = min\n    return'),
 GOOD.replace('max(0, min(requested, pending, hard_limit))','lambda: 1'),
 'def bounded_batch_size(requested, pending, hard_limit):\n'+'    if requested:\n'*80+'        return 1\n',
])
def test_rejects_host_access_unbounded_or_non_integer_semantics(source):
    result=check_function({'source':source,'profile_id':'bounded_batch_size.v1'})
    assert result['accepted'] is False

def test_caller_cannot_supply_cases_or_forged_profile():
    with pytest.raises(ValueError):check_function({'source':GOOD,'profile_id':'bounded_batch_size.v1','cases':[]})
    with pytest.raises(ValueError):check_function({'source':GOOD,'profile_id':'invented'})

def test_receipt_validator_refuses_completed_claim_without_execution():
    from types import SimpleNamespace
    engine=SimpleNamespace(missions=SimpleNamespace(get=lambda _:{}))
    with pytest.raises(ValueError):validated_acceptance(engine,'fake',1,'check')

def test_real_governed_executor_registration_receipt_and_independent_recomputation(tmp_path,monkeypatch):
    from backend.runtime.execution import execute_request,verify_request_result
    monkeypatch.chdir(tmp_path)
    task={'id':'real-check','prompt':'Check bounded function','metadata':{'tool':TOOL,'tool_parameters':{'source':GOOD,'profile_id':'bounded_batch_size.v1'}}}
    result=execute_request(task,{'compute'})
    assert result['output']['accepted'] is True
    assert verify_request_result(task,result)['state']=='VERIFIED'
    with pytest.raises(PermissionError):execute_request(dict(task,id='no-grant'),set())
    result['output']['cases_passed']=0
    with pytest.raises(ValueError):verify_request_result(task,result)

@pytest.mark.parametrize('expression',[
 'max(0, min(requested, pending, hard_limit))',
 '(requested and pending) or hard_limit',
 'requested if requested < pending < hard_limit else pending',
 'pending if requested > 0 and pending > 0 else hard_limit',
 'requested if not (pending < 0) else hard_limit',
])
def test_reviewed_subset_matches_python_short_circuit_and_chained_comparison_semantics(expression):
    from backend.runtime.bounded_function_tests import Interpreter
    source=GOOD.replace('max(0, min(requested, pending, hard_limit))',expression)
    # Trusted test expressions only. Production never compiles or executes Python.
    namespace={};exec(compile(source,'<trusted-subset-test>','exec'),namespace)
    interpreter=Interpreter(source)
    for args in ((1,2,3),(-3,0,4),(0,0,5),(5,4,3)):
        assert interpreter.run(args)==namespace['bounded_batch_size'](*args)
    with pytest.raises(ValueError):interpreter.run((True,1,2))
    with pytest.raises(ValueError):interpreter.run([1,2,3])

def test_restart_requeues_same_pure_check_id_without_replaying_models_writes_or_processes(tmp_path):
    from types import SimpleNamespace
    from backend.storage.db import Database
    from backend.storage.repository import TaskRepository
    from backend.runtime.tasks import TaskManager
    from backend.runtime.engine import RuntimeEngine
    database=Database(tmp_path/'restart.db');repository=TaskRepository(database)
    tasks=TaskManager(repository);ids={}
    for tool in (TOOL,None,'workspace.write@1.0.0','process.run@1.0.0'):
        task=tasks.create('Retained checkpoint',{'tool':tool});tasks.transition_task(task['id'],'running');ids[tool]=task['id']
    restored=TaskManager(repository)
    engine=SimpleNamespace(tasks=restored,events=SimpleNamespace(publish=lambda *args:None))
    RuntimeEngine.reconcile_startup_tasks(engine)
    assert restored.get(ids[TOOL])['status']=='queued'
    for tool in (None,'workspace.write@1.0.0','process.run@1.0.0'):
        assert restored.get(ids[tool])['status']=='RECOVERY_REQUIRED'
    assert len(restored.list())==4

@pytest.mark.parametrize('repair', [False,True])
@pytest.mark.parametrize('formatting', ['raw','python_fence','prose','multiple','generic','repair_prose','wrong_language','trailing_prose'])
def test_persistent_native_model_write_read_check_receipt_and_repair(tmp_path,monkeypatch,repair,formatting):
    from types import SimpleNamespace
    from backend.storage.db import Database
    from backend.storage.repository import TaskRepository
    from backend.runtime.tasks import TaskManager
    from backend.runtime.missions import MissionPlan,MissionService
    from backend.runtime.execution import execute_request,verify_request_result
    from backend.models.service import ModelService
    from backend.swarm.manager import execution_request
    monkeypatch.chdir(tmp_path);monkeypatch.setenv('KINGDOM_WORKSPACE',str(tmp_path/'workspace'))
    database=Database(tmp_path/'state.db');tasks=TaskManager(TaskRepository(database))
    policy={'level':5,'mission_budget':{'max_steps':20,'max_parallel':1,'max_retries':1,'auto_advance':True}}
    engine=SimpleNamespace(tasks=tasks,execution_policy=SimpleNamespace(get=lambda:policy),events=SimpleNamespace(publish=lambda *args:None),submit_task=tasks.create)
    service=engine.missions=MissionService(engine,database)
    candidates=[GOOD.replace('max(0, min(requested, pending, hard_limit))','requested'),GOOD] if repair else [GOOD]
    if formatting!='raw':candidates=['```python\n'+candidate+'```\n' for candidate in candidates]
    if formatting=='prose':candidates=['Here is the implementation:\n'+candidate for candidate in candidates]
    if formatting=='multiple':candidates=[candidate+'```python\n'+GOOD+'```\n' for candidate in candidates]
    if formatting=='wrong_language':candidates=[candidate.replace('```python','```javascript') for candidate in candidates]
    if formatting=='trailing_prose':candidates=[candidate+'That should fix it.\n' for candidate in candidates]
    if formatting=='repair_prose' and repair:candidates[1]='Here is the repair:\n'+candidates[1]
    responses=iter(candidates)
    async def provider_response(*args,**kwargs):return {'text':next(responses)}
    monkeypatch.setattr(ModelService,'generate',provider_response)
    plan=MissionPlan(title='Batch size',objective='Implement bounded batch size',deliverables=['batch.py'],steps=[
      {'id':'generate','title':'Generate','kind':'model','instructions':'Write the integer function','acceptance':'Candidate'},
      {'id':'write','title':'Write','kind':'write_file','path':'batch.py','depends_on':['generate'],'input_from':'generate','acceptance':'Governed source'},
      {'id':'read','title':'Read','kind':'read_file','path':'batch.py','depends_on':['write'],'acceptance':'Read back'},
      {'id':'check','title':'Check fixed owner cases','kind':'function_check','depends_on':['write','read'],'input_from':'read','repair_source':'write','case_profile':'bounded_batch_size.v1','acceptance':'26 fixed integer cases'},
    ])
    if formatting=='generic':plan.steps=plan.steps[:-1]
    state=service.create(plan,model_profile='non-toolcalling-local');service.approve(state['id'],1)
    seen=[]
    for _ in range(30):
        state=service.advance(state['id'])
        if formatting in {'prose','multiple','wrong_language','trailing_prose'}:
            assert 'workspace.write@1.0.0' not in seen
            if state['status']=='needs_review':
                assert not (tmp_path/'workspace/batch.py').exists()
                return
        if formatting=='repair_prose' and repair and state['status']=='needs_review':
            assert (tmp_path/'workspace/batch.py').read_text()==GOOD.replace('max(0, min(requested, pending, hard_limit))','requested')
            assert len(state['source_normalizations'])==1 and len(state['repair_history'])==1
            return
        if state['status']=='completed':break
        assert state['status'] not in {'needs_review','cancelled'},state
        task=tasks.claim_next()
        if not task:continue
        seen.append(task['metadata'].get('tool','model'))
        request=execution_request(task,task['prompt'])
        outcome=execute_request(request,{'compute','filesystem.read','filesystem.write','model.inference'})
        verification=verify_request_result(request,outcome)
        tasks.complete(task['id'],{'plan':{'task_id':task['id'],'subtasks':[{'prompt':task['prompt'],'knight':'coder'}]},'results':[{'knight':'coder','verification':verification,'outcome':outcome}]})
    assert state['status']=='completed'
    if formatting=='generic':
        assert (tmp_path/'workspace/batch.py').read_bytes()==candidates[0].encode()
        assert not state.get('source_normalizations')
        return
    if formatting=='python_fence':
        provenance=state['source_normalizations']
        assert len(provenance)==(2 if repair else 1)
        assert all(item['format']=='single_python_fence' and item['raw_sha256']!=item['source_sha256'] for item in provenance)
        assert all('```python' in service.output(tasks.get(item['model_task_id'])) for item in provenance)
    assert 'process.run@1.0.0' not in seen
    assert len(state.get('repair_history',[]))==(1 if repair else 0)
    # A separately restored task/mission store still validates actual retained receipts.
    engine.tasks=TaskManager(TaskRepository(database));engine.missions=MissionService(engine,database)
    accepted=validated_acceptance(engine,state['id'],1,'check')
    assert accepted['cases_passed']==accepted['cases_run']==26
    assert accepted['executor_scope']=='bounded arithmetic AST interpreter; not CPython/arbitrary repo'
    with pytest.raises(ValueError):validated_acceptance(engine,state['id'],2,'check')
    (tmp_path/'workspace/batch.py').write_text(GOOD+'# external change\n')
    with pytest.raises(ValueError):validated_acceptance(engine,state['id'],1,'check')
