import json
import pytest
from test_agent_sessions import setup,reply,call


@pytest.mark.asyncio
async def test_missing_path_is_feedback_not_claimed_execution(setup):
    service,engine,_=setup([reply(calls=[call('workspace_list',{'path':'tests'})]),reply('Use the supplied test file instead.')])
    state=await service.advance(service.create('Inspect','model')['id'])
    ident=state['pending'][0]['task_id']
    engine.records[ident].update(status='failed',error="[Errno 2] No such file or directory: 'tests'")
    state=await service.advance(state['id'])
    assert state['status']=='ready' and not state['pending']
    output=json.loads(state['messages'][-1]['content'])
    assert output['error_code']=='path_not_found' and 'verification' not in output
    assert len(engine.records)==1


@pytest.mark.asyncio
@pytest.mark.parametrize('tool,args,error',[('workspace_read',{'path':'a.py'},'No Apprentice has the required computer-tool grant'),('workspace_write',{'path':'a.py','content':'x'},'[Errno 2] No such file or directory')])
async def test_review_does_not_replay_permissions_or_failed_writes(setup,tool,args,error):
    service,engine,_=setup([reply(calls=[call(tool,args)])])
    state=await service.advance(service.create('Inspect','model')['id'])
    engine.records[state['pending'][0]['task_id']].update(status='failed',error=error)
    state=await service.advance(state['id'])
    with pytest.raises(ValueError):service.review_feedback(state['id'],'Try again',state['updated_at'])
    assert len(engine.records)==1 and service.get(state['id'])['status']=='needs_review'


def test_feedback_requires_exact_checkpoint_and_preserves_budget(setup):
    service,_,_=setup([])
    state=service.create('Repair','auto');state.update(status='needs_review',turns=2,error='Model unavailable');service._save(state)
    with pytest.raises(ValueError):service.review_feedback(state['id'],'Model host restored',0)
    current=service.get(state['id']);result=service.review_feedback(current['id'],'Model host restored',current['updated_at'])
    assert result['turns']==2 and result['status']=='ready'
    assert result['messages'][-1]['role']=='user'


def test_completed_response_can_receive_independent_test_failure(setup):
    service,engine,_=setup([])
    state=service.create('Repair','auto',max_turns=4)
    state.update(status='completed',turns=3);service._save(state)
    current=service.get(state['id'])
    resumed=service.review_feedback(current['id'],'Independent tests failed: SyntaxError at line 19',current['updated_at'])
    assert resumed['status']=='ready' and resumed['turns']==3
    assert not engine.records
    resumed.update(status='completed',turns=4);service._save(resumed)
    current=service.get(state['id'])
    with pytest.raises(ValueError,match='budget exhausted'):
        service.review_feedback(current['id'],'Keep trying',current['updated_at'])


def test_coding_setup_and_review_require_owner():
    from fastapi.testclient import TestClient
    from backend.main import app
    client=TestClient(app)
    assert client.get('/agent-sessions/readiness').status_code in {401,403}
    assert client.post('/agent-sessions/example/review-feedback',json={
        'message':'retry','expected_updated_at':0}).status_code in {401,403}


@pytest.mark.asyncio
async def test_review_accepts_mixed_completed_read_and_wrong_path_type(setup):
    service,engine,_=setup([reply(calls=[call('workspace_list',{'path':'a.py'},'list'),call('workspace_read',{'path':'test.py'},'read')])])
    state=await service.advance(service.create('Inspect','model')['id'])
    engine.records[state['pending'][0]['task_id']].update(status='failed',error="[Errno 20] Not a directory: 'a.py'")
    engine.finish(state['pending'][1]['task_id'],{'text':'tests'})
    state.update(status='needs_review');service._save(state)
    current=service.get(state['id'])
    result=service.review_feedback(current['id'],'Read the file instead of listing it',current['updated_at'])
    assert result['status']=='ready' and not result['pending'] and len(engine.records)==2
    assert 'failed observation' in result['messages'][-3]['content']


@pytest.mark.asyncio
async def test_claimed_edit_without_actual_write_cannot_complete(setup):
    service,engine,_=setup([reply('I saved the fix.')])
    state=await service.advance(service.create('Edit source','model',required_tools=['workspace_write'])['id'])
    assert state['status']=='needs_review' and 'workspace_write' in state['error']
    assert not engine.records


@pytest.mark.asyncio
async def test_verified_write_satisfies_requirement_but_not_next_review(setup):
    service,engine,_=setup([reply(calls=[call('workspace_write',{'path':'a.py','content':'x'})]),reply('Written'),reply('Fixed again')])
    state=await service.advance(service.create('Edit source','model',required_tools=['workspace_write'])['id'])
    engine.finish(state['pending'][0]['task_id'],{'path':'a.py'})
    await service.advance(state['id']);state=await service.advance(state['id'])
    assert state['status']=='completed'
    state=service.review_feedback(state['id'],'Independent tests failed',state['updated_at'])
    state=await service.advance(state['id'])
    assert state['status']=='needs_review' and len(engine.records)==1
