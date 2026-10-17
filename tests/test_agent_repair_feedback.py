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
