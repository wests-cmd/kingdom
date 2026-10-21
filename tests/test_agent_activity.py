import time
import pytest
from test_agent_sessions import setup, reply, call


def test_activity_explains_wait_and_separates_model_from_tools(setup):
    service, _, _ = setup([])
    state=service.create('Inspect','local')
    state.update(status='thinking',model_started_at=time.time()-90)
    service._save(state)
    activity=service.activity(state['id'])
    assert activity['status_label']=='Waiting for model'
    assert activity['model_wait_seconds']>=89
    assert activity['verified_actions']==0
    assert activity['model_connection']=='local'
    assert activity['tool_host'] and activity['tool_platform']
    assert 'No tool execution' in activity['evidence_summary']
    assert 'slow' in activity['attention'].lower()


def test_text_completion_is_not_verified_task_completion(setup):
    service, _, _ = setup([])
    state=service.create('Fix code','local')
    state.update(status='completed',answer='All done. Tests passed.')
    service._save(state)
    activity=service.activity(state['id'])
    assert activity['status_label']=='Response finished'
    assert activity['verified_actions']==0
    assert activity['acceptance_checks']==[]
    assert 'No required' in activity['attention']
    assert 'No tool execution' in activity['evidence_summary']
    assert not activity['independent_tests_verified']


def test_activity_does_not_leak_prompts_arguments_or_task_errors(setup):
    service, engine, _ = setup([])
    state=service.create('password=TOPSECRET','local')
    state.update(status='waiting_tools',pending=[{'name':'workspace_read','task_id':'test-id','arguments':{'secret':'TOPSECRET'}}])
    engine.records['test-id']={'id':'test-id','status':'WAITING_APPROVAL','metadata':{'actor_id':'coder'},'error':'token=TOPSECRET'}
    service._save(state)
    activity=service.activity(state['id'])
    assert activity['status_label']=='Approval needed'
    assert activity['operations'][0]['status']=='waiting_approval'
    assert 'TOPSECRET' not in str(activity)


@pytest.mark.asyncio
async def test_observation_expiration_has_visible_specific_error(setup):
    service, engine, _ = setup([reply(calls=[call('desktop_input',{'action':'key','key':'tab'})])])
    state=service.create('Use window','local',desktop_window_title='Test')
    state.update(desktop_observation_required=False,desktop_observation={'window_handle':123,'observed_at':time.time()-100})
    service._save(state)
    state=await service.advance(state['id'])
    assert state['status']=='needs_review'
    assert state['error_code']=='desktop_observation_expired'
    activity=service.activity(state['id'])
    assert 'fresh' in activity['next_action'].lower()
    assert 'expired' in activity['blocker'].lower()
    assert not engine.records

@pytest.mark.asyncio
async def test_empty_listing_and_written_diagnosis_remain_visibly_unverified(setup):
    service,engine,_=setup([reply(calls=[call('workspace_list',{'path':'.'},'list')]),reply(calls=[call('workspace_write',{'path':'diagnosis.md','content':'I confirmed the cause.'},'write')])])
    state=await service.advance(service.create('Diagnose','local')['id'])
    engine.finish(state['pending'][0]['task_id'],{'path':'.','entries':[]})
    await service.advance(state['id']);state=await service.advance(state['id'])
    engine.finish(state['pending'][0]['task_id'],{'path':'diagnosis.md','sha256':'real-file-hash'})
    await service.advance(state['id'])
    activity=service.activity(state['id'])
    assert activity['verified_actions']==2
    assert activity['source_reads']==0 and activity['file_writes']==1
    assert activity['empty_directory_observed'] is True
    assert 'written diagnosis is not evidence' in activity['attention']
    assert not activity['independent_tests_verified']


def test_activity_endpoint_requires_owner():
    from fastapi.testclient import TestClient
    from backend.main import app
    client=TestClient(app)
    assert client.get('/agent-sessions/example/activity').status_code in {401,403}


@pytest.mark.asyncio
async def test_invalid_arguments_report_category_without_secret_values(setup):
    service,engine,_=setup([reply(calls=[call('desktop_input',{'action':'key','key':'PASSWORD_SECRET'})])])
    state=service.create('Use window','local',desktop_window_title='Test')
    state.update(desktop_observation_required=False,desktop_observation={'window_handle':123,'observed_at':time.time()})
    service._save(state)
    state=await service.advance(state['id'])
    assert state['error_code']=='invalid_tool_arguments'
    assert 'PASSWORD_SECRET' not in str(service.activity(state['id']))
    assert not engine.records
