import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.runtime.work_programmes import WorkProgrammes
from backend.models.profiles import ModelProfiles
from test_project_test_missions import runtime


def setup(runtime,monkeypatch):
    engine,backlog,_=runtime
    profile={'id':'local','provider':'ollama','endpoint':'http://127.0.0.1:11434',
             'model':'small','hosting':'local','auto_select':True}
    monkeypatch.setattr(ModelProfiles,'get',lambda self,ident,**kwargs:profile)
    service=WorkProgrammes(backlog.db,engine,backlog)
    state=service.create('kingdom','standing-scope','- Implement bounded_batch_size helper',model_profile='local')
    proposal={'title':'Bounded helper','objective':'Implement bounded batch helper','deliverables':['candidate'],
      'steps':[
        {'id':'write','title':'Write candidate','kind':'write_file','path':'projects/standing/candidate.py',
         'instructions':'model source is data','acceptance':'Governed write'},
        {'id':'read','title':'Read candidate','kind':'read_file','path':'projects/standing/candidate.py',
         'depends_on':['write'],'acceptance':'Retained read hash'},
        {'id':'check','title':'Immutable cases','kind':'function_check','depends_on':['write','read'],
         'input_from':'read','repair_source':'write','case_profile':'bounded_batch_size.v1','acceptance':'All cases'}]}
    row=state['sections'][0]['items'][0]
    state=service.get(state['id'])
    row=state['sections'][0]['items'][0]
    from backend.runtime.missions import MissionPlan,validate_plan
    row.update(planning='needs_review',proposal=validate_plan(MissionPlan.model_validate(proposal)).model_dump(),acceptance_step='check',
      planning_stages={name:{'profile':'local','hosting':'local','text':'proposal'} for name in ['plan_a','plan_b','critique','synthesis']})
    service._save(state,state['revision'])
    return engine,backlog,service,service.get(state['id']),proposal


def scope():return {'enabled':True,'write_prefix':'projects/standing','read_sources':{},'max_missions':2}


def test_owner_scope_reviews_bounded_plan_and_binds_without_model_permission(runtime,monkeypatch):
    engine,backlog,service,state,_=setup(runtime,monkeypatch)
    service.configure_standing_review(state['id'],scope(),state['revision'])
    asyncio.run(service.tick())
    state=service.get(state['id']);row=state['sections'][0]['items'][0]
    assert row['planning']=='reviewed'
    assert row['review_basis']['kind']=='owner-scoped-function-policy-v1'
    assert engine.missions.get(row['mission_id'])['status']=='approved'
    assert backlog.get('kingdom',row['work_id'])['enabled'] is True
    assert state['standing_review']['used_missions']==1
    assert engine.tasks.list()==[]


def test_no_standing_scope_leaves_owner_review_required(runtime,monkeypatch):
    engine,_,service,state,_=setup(runtime,monkeypatch)
    asyncio.run(service.tick())
    assert service.get(state['id'])['sections'][0]['items'][0]['planning']=='needs_review'
    assert engine.missions.list()==[]


@pytest.mark.parametrize('change',['outside_path','command','unknown_cases','cloud'])
def test_standing_review_rejects_scope_expansion(runtime,monkeypatch,change):
    engine,_,service,state,_=setup(runtime,monkeypatch)
    service.configure_standing_review(state['id'],scope(),state['revision'])
    state=service.get(state['id']);row=state['sections'][0]['items'][0]
    if change=='outside_path':row['proposal']['steps'][0]['path']='projects/other/candidate.py'
    elif change=='command':row['proposal']['steps'].insert(0,{'id':'shell','title':'Run','kind':'command','argv':['sh','-c','anything'],'acceptance':'claim'})
    elif change=='unknown_cases':row['proposal']['steps'][-1]['case_profile']='model-supplied'
    else:
        row['planning_stages']['plan_a']['hosting']='cloud'
    service._save(state,state['revision'])
    asyncio.run(service.tick())
    row=service.get(state['id'])['sections'][0]['items'][0]
    assert row['planning']=='needs_review' and row.get('standing_review_denial')
    assert engine.missions.list()==[] and engine.tasks.list()==[]


def test_standing_scope_revocation_blocks_further_mission_dispatch(runtime,monkeypatch):
    engine,_,service,state,_=setup(runtime,monkeypatch)
    service.configure_standing_review(state['id'],scope(),state['revision'])
    asyncio.run(service.tick())
    state=service.get(state['id']);row=state['sections'][0]['items'][0]
    service.configure_standing_review(state['id'],{**scope(),'enabled':False},state['revision'])
    with pytest.raises(ValueError,match='Programme review'):
        engine.missions.advance(row['mission_id'])
    assert engine.tasks.list()==[]


def test_standing_review_requires_owner_level_and_honours_quota(runtime,monkeypatch):
    engine,_,service,state,_=setup(runtime,monkeypatch)
    policy=engine.execution_policy.get()
    policy['level']=3
    with pytest.raises(ValueError,match='level5'):
        service.configure_standing_review(state['id'],scope(),state['revision'])
    policy['level']=5
    service.configure_standing_review(state['id'],scope(),state['revision'])
    state=service.get(state['id']);state['standing_review']['used_missions']=2
    service._save(state,state['revision'])
    asyncio.run(service.tick())
    assert engine.missions.list()==[]


def test_model_profile_change_revokes_standing_dispatch(runtime,monkeypatch):
    engine,_,service,state,_=setup(runtime,monkeypatch)
    service.configure_standing_review(state['id'],scope(),state['revision'])
    asyncio.run(service.tick())
    row=service.get(state['id'])['sections'][0]['items'][0]
    monkeypatch.setattr(ModelProfiles,'get',lambda *args,**kwargs:
        {'id':'local','provider':'ollama','endpoint':'https://other.example','model':'small','hosting':'cloud'})
    with pytest.raises(ValueError,match='Programme review'):engine.missions.advance(row['mission_id'])
    assert engine.tasks.list()==[]


def test_owner_read_source_hash_is_checked_before_later_dispatch(runtime,monkeypatch):
    import hashlib
    engine,_,service,state,_=setup(runtime,monkeypatch)
    workspace=runtime[2]
    source=workspace/'projects/accepted/source.py';source.parent.mkdir(parents=True);source.write_text('accepted data')
    scope_value={**scope(),'read_sources':{'projects/accepted/source.py':hashlib.sha256(source.read_bytes()).hexdigest()}}
    service.configure_standing_review(state['id'],scope_value,state['revision'])
    state=service.get(state['id']);row=state['sections'][0]['items'][0]
    row['proposal']['steps'].insert(0,{'id':'source','kind':'read_file','title':'Read accepted source',
        'path':'projects/accepted/source.py','acceptance':'Exact digest'})
    row['proposal']['steps'][1].update(depends_on=['source'],input_from='source')
    service._save(state,state['revision'])
    asyncio.run(service.tick())
    row=service.get(state['id'])['sections'][0]['items'][0]
    assert row['planning']=='reviewed'
    source.write_text('changed')
    with pytest.raises(ValueError,match='Programme review'):engine.missions.advance(row['mission_id'])
    assert engine.tasks.list()==[]


def test_compact_blueprint_is_compiled_validated_and_reviewed_as_proposal(runtime,monkeypatch):
    import hashlib
    from backend.runtime.work_blueprints import compile_function_copy
    engine,backlog,workspace=runtime
    profile={'id':'local','provider':'ollama','endpoint':'http://127.0.0.1:11434','model':'small','hosting':'local','auto_select':True}
    monkeypatch.setattr(ModelProfiles,'get',lambda self,ident,**kw:{**profile,'api_key':''})
    monkeypatch.setattr(ModelProfiles,'list',lambda self:[profile])
    monkeypatch.setattr('backend.models.selection.availability',AsyncMock(return_value={'available':True,'retryable':False}))
    source=workspace/'projects/accepted/candidate.py';source.parent.mkdir(parents=True);source.write_text('accepted source')
    service=WorkProgrammes(backlog.db,engine,backlog)
    state=service.create('kingdom','compact-blueprint',
        '- Copy bounded_batch_size from projects/accepted/candidate.py to projects/standing/candidate.py and check immutable cases.',model_profile='local')
    service.configure_standing_review(state['id'],{**scope(),'read_sources':{'projects/accepted/candidate.py':hashlib.sha256(source.read_bytes()).hexdigest()}},state['revision'])
    state=service.get(state['id'])
    choice={'blueprint':'function_copy.v1','source':'projects/accepted/candidate.py','target':'projects/standing/candidate.py'}
    engine.models=SimpleNamespace(plan_chat=AsyncMock(side_effect=[{'text':'A'},{'text':'B'},{'text':'gaps'},{'text':'```json\n'+json.dumps(choice)+'\n```'}]))
    result=asyncio.run(service.plan_next(state['id'],state['revision']))
    row=result['sections'][0]['items'][0]
    assert row['planning']=='needs_review' and row['proposal']['steps'][-1]['case_profile']=='bounded_batch_size.v1'
    assert len(engine.models.plan_chat.await_args_list[0].args[0])<2000
    asyncio.run(service.tick())
    assert service.get(state['id'])['sections'][0]['items'][0]['planning']=='reviewed'
    assert engine.tasks.list()==[]  # Review/binding is distinct from actual execution.
    with pytest.raises(ValueError):compile_function_copy({**choice,'argv':['sh']},'outcome')


def test_owner_can_disable_scope_after_model_is_removed(runtime,monkeypatch):
    _,_,service,state,_=setup(runtime,monkeypatch)
    service.configure_standing_review(state['id'],scope(),state['revision'])
    monkeypatch.setattr(ModelProfiles,'get',lambda *a,**kw:(_ for _ in ()).throw(KeyError('missing')))
    state=service.get(state['id'])
    result=service.configure_standing_review(state['id'],{**scope(),'enabled':False},state['revision'])
    assert result['standing_review']['scope']['enabled'] is False


def test_revocation_after_queueing_is_checked_at_execution_authorization(runtime,monkeypatch):
    from backend.runtime.engine import RuntimeEngine
    engine,backlog,service,state,_=setup(runtime,monkeypatch)
    engine.security=SimpleNamespace(authorize=lambda **kwargs:{'authorized':True},
        nodes=SimpleNamespace(get_node=lambda _: {'token':'unused'}))
    engine.execution_policy.requires_approval=lambda _:False
    service.configure_standing_review(state['id'],scope(),state['revision'])
    asyncio.run(service.tick())
    backlog.settings(True,backlog.snapshot()['revision'])
    backlog.tick()
    task=engine.tasks.claim_next()
    assert task is not None and RuntimeEngine.authorize_task(engine,task)['authorized'] is True
    state=service.get(state['id'])
    service.configure_standing_review(state['id'],{**scope(),'enabled':False},state['revision'])
    assert RuntimeEngine.authorize_task(engine,task)['authorized'] is False
