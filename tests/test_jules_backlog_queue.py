"""Durable owner-scoped admission over the real backlog and Jules job store."""
from types import SimpleNamespace
import pytest
from backend.storage.db import Database
from backend.runtime.work_backlog import WorkBacklog
from backend.integrations.jules import JulesService
from backend.integrations.jules_backlog import JulesBacklogQueue


def test_restart_cancel_and_dependencies_admit_next_independent_item(tmp_path):
    db=Database(tmp_path/'queue.db')
    engine=SimpleNamespace(execution_policy=SimpleNamespace(get=lambda:{'level':5}),events=SimpleNamespace(publish=lambda *a:None))
    service=JulesService(db,engine=engine,secrets_root=tmp_path/'secrets',clock=lambda:1000)
    service.configure(api_key='test-only-credential',enabled=True)
    backlog=WorkBacklog(db,engine)
    first=backlog.register('kingdom','first',title='First',description='Implement first task')
    dependent=backlog.register('kingdom','dependent',title='Dependent',description='Needs first acceptance',depends_on=[first['id']])
    independent=backlog.register('kingdom','independent',title='Independent',description='Implement another task')
    queue=JulesBacklogQueue(service)
    scope=dict(project='kingdom',idempotency_key='owner-batch',repository='wests-cmd/kingdom',source='sources/github/wests-cmd/kingdom',revision='a'*40,branch='main',items=[{'backlog_id':r['id'],'expected_revision':r['revision']} for r in (first,dependent,independent)],deadline_seconds=3600)
    batch=queue.create(**scope)
    queue.tick()
    jobs=service.list_jobs();assert len(jobs)==1 and jobs[0]['backlog_id']==first['id']
    queue=JulesBacklogQueue(JulesService(db,engine=engine,secrets_root=tmp_path/'secrets',clock=lambda:1000))
    queue.tick();assert len(service.list_jobs())==1
    service.cancel_job(jobs[0]['id'])
    queue.tick()
    jobs=service.list_jobs();assert len(jobs)==2
    assert {j['backlog_id'] for j in jobs}=={first['id'],independent['id']}
    assert queue.create(**scope)['id']==batch['id']
    assert backlog.get('kingdom',dependent['id'])['status']=='needs_planning'
    assert all(j['accepted'] is False for j in jobs)


@pytest.fixture
def batch(tmp_path):
    now=[1000.0]
    db=Database(tmp_path/'queue.db')
    level=[5]
    engine=SimpleNamespace(execution_policy=SimpleNamespace(get=lambda:{'level':level[0]}),events=SimpleNamespace(publish=lambda *a:None))
    service=JulesService(db,engine=engine,secrets_root=tmp_path/'secrets',clock=lambda:now[0])
    service.configure(api_key='test-only-key',enabled=True)
    backlog=WorkBacklog(db,engine)
    notes=[backlog.register('kingdom','n'+str(i),title='Task '+str(i),description='Scoped implementation '+str(i)) for i in range(2)]
    queue=JulesBacklogQueue(service)
    scope=dict(project='kingdom',idempotency_key='batch',repository='wests-cmd/kingdom',source='sources/github/wests-cmd/kingdom',revision='a'*40,branch='main',items=[{'backlog_id':r['id'],'expected_revision':r['revision']} for r in notes],deadline_seconds=3600)
    state=queue.create(**scope)
    return queue,service,backlog,notes,state,scope,now,level


def test_pause_revocation_and_changed_note_prevent_new_dispatch(batch):
    queue,service,backlog,notes,state,scope,now,level=batch
    queue.configure(state['id'],False,state['binding']);queue.tick()
    assert service.list_jobs()==[]
    queue.configure(state['id'],True,state['binding'])
    level[0]=0;queue.tick();assert service.list_jobs()==[]
    level[0]=5
    from backend.runtime.work_programmes import WorkProgrammes
    WorkProgrammes(backlog.db,service.engine,backlog).adopt('kingdom','other-programme',
        [{'work_id':notes[0]['id'],'expected_revision':notes[0]['revision']}],title='Other owner workflow',source_revision='a'*40)
    queue.tick()
    assert [j['backlog_id'] for j in service.list_jobs()]==[notes[1]['id']]
    assert queue.list()[0]['items'][0]['phase']=='review_required'


def test_expiry_and_scope_idempotency_are_not_renewable(batch):
    queue,service,backlog,notes,state,scope,now,level=batch
    with pytest.raises(ValueError):queue.create(**{**scope,'revision':'b'*40})
    now[0]=5000;queue.tick()
    assert service.list_jobs()==[]
    with pytest.raises(ValueError):queue.configure(state['id'],True,state['binding'])
    assert queue.create(**scope)['enabled'] is False


def test_remote_completion_and_unknown_cancel_never_release_slot(batch):
    queue,service,backlog,notes,state,scope,now,level=batch
    queue.tick();job=service.list_jobs()[0]
    class Response:
        def __init__(self,value):self.value=value
        def read(self,*args):return __import__('json').dumps(self.value).encode()
        def __enter__(self):return self
        def __exit__(self,*a):pass
    class Provider:
        def open(self,request,timeout=30):
            return Response({'name':'sessions/test-remote','state':'COMPLETED','url':'https://jules.google.com/session/test-remote'})
    # Only external provider transport is substituted; real submit/poll/cancel and queue persist.
    service.submit_job(job['id'],opener=Provider())
    service.poll_job(job['id'],opener=Provider())
    queue.tick();assert len(service.list_jobs())==1
    assert service.get_job(job['id'])['accepted'] is False
    service.cancel_job(job['id']);queue.tick()
    assert len(service.list_jobs())==1


def test_registration_crash_rolls_back_and_restart_creates_one_job(batch,monkeypatch):
    queue,service,backlog,notes,state,scope,now,level=batch
    original=service.register_job
    def crash(**values):
        result=original(**values)
        raise RuntimeError('Injected crash after insert before atomic admission commit')
    monkeypatch.setattr(service,'register_job',crash)
    with pytest.raises(RuntimeError):queue.tick()
    assert len(service.list_jobs())==0
    monkeypatch.setattr(service,'register_job',original)
    now[0]+=20
    restarted=JulesBacklogQueue(service);restarted.tick()
    assert len(service.list_jobs())==1
    assert restarted.list()[0]['items'][0]['job_id']==service.list_jobs()[0]['id']


def test_two_queue_instances_do_not_create_duplicate_admissions(batch):
    from concurrent.futures import ThreadPoolExecutor
    queue,service,*_=batch
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _:JulesBacklogQueue(service).tick(),range(2)))
    assert len(service.list_jobs())==1


def test_public_owner_api_rejects_unauthorized_scope_and_extra_authority(batch,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.integrations import jules_api
    from backend.security.http_auth import owner_auth
    queue,service,backlog,notes,state,scope,now,level=batch
    monkeypatch.setattr(jules_api,'service',lambda:service)
    app=FastAPI();app.include_router(jules_api.router);client=TestClient(app)
    path='/integrations/jules/backlog-queues'
    assert client.get(path).status_code==401
    assert client.post(path,json=scope).status_code==403
    assert client.post(path,json=scope,headers={'X-Kingdom-Request':'1'}).status_code==401
    headers={'Authorization':'Bearer '+owner_auth.token,'X-Kingdom-Request':'1'}
    assert client.post(path,json=scope,headers=headers).status_code==201
    assert client.post(path,json={**scope,'automatic_merge':True},headers=headers).status_code==422
    assert client.post(path,json={**scope,'repository':'elsewhere/private'},headers=headers).status_code==409
    assert client.post(path,json=scope,headers={**headers,'Origin':'https://untrusted.example'}).status_code==403
    paused=client.post(path+'/'+state['id']+'/settings',json={'enabled':False,'expected_binding':state['binding']},headers=headers)
    assert paused.status_code==200 and paused.json()['enabled'] is False
    assert 'test-only-key' not in client.get(path,headers=headers).text


def test_recovered_admission_never_extends_batch_deadline(batch,monkeypatch):
    queue,service,backlog,notes,state,scope,now,level=batch
    original=service.register_job
    def crash_before(**values):raise RuntimeError('Crash before registration')
    monkeypatch.setattr(service,'register_job',crash_before)
    with pytest.raises(RuntimeError):queue.tick()
    now[0]+=100
    monkeypatch.setattr(service,'register_job',original)
    JulesBacklogQueue(service).tick()
    assert service.list_jobs()[0]['deadline_at']<=state['deadline_at']


def test_crash_after_admission_commit_rejoins_same_job(batch,monkeypatch):
    queue,service,backlog,notes,state,scope,now,level=batch
    original=service._announce
    def crash(*a,**kw):raise RuntimeError('Crash publishing event after commit')
    monkeypatch.setattr(service,'_announce',crash)
    with pytest.raises(RuntimeError):queue.tick()
    assert len(service.list_jobs())==1
    monkeypatch.setattr(service,'_announce',original)
    now[0]+=100;JulesBacklogQueue(service).tick()
    assert len(service.list_jobs())==1


def test_delayed_registration_cannot_extend_absolute_owner_window(batch,monkeypatch):
    queue,service,backlog,notes,state,scope,now,level=batch
    original=service.register_job
    def delayed(**values):
        now[0]+=100
        return original(**values)
    monkeypatch.setattr(service,'register_job',delayed)
    queue.tick()
    assert service.list_jobs()[0]['deadline_at']<=state['deadline_at']


def test_last_seconds_do_not_leave_an_admission_that_stalls_other_batches(batch):
    queue,service,backlog,notes,state,scope,now,level=batch
    now[0]=state['deadline_at']-59
    queue.tick();assert service.list_jobs()==[]
    note=backlog.register('kingdom','fresh',title='Fresh independent work',description='Another owner outcome')
    queue.create(**{**scope,'idempotency_key':'fresh','items':[{'backlog_id':note['id'],'expected_revision':note['revision']}]})
    queue.tick()
    assert [j['backlog_id'] for j in service.list_jobs()]==[note['id']]


from test_project_test_missions import runtime,plan,start,execute

@pytest.mark.parametrize('when',['before_admission','before_submission'])
def test_dependency_acceptance_is_rechecked_against_real_process_receipt(runtime,when,tmp_path):
    engine,backlog,workspace=runtime
    mission,prerequisite=start(engine,backlog,plan())
    task=execute(engine);backlog.tick()
    assert backlog.get('kingdom',prerequisite['id'])['status']=='completed'
    note=backlog.register('kingdom','dependent-coding',title='Dependent code',description='Code only after current accepted tests',depends_on=[prerequisite['id']])
    service=JulesService(backlog.db,engine=engine,secrets_root=tmp_path/'queue-secret')
    service.configure(api_key='test-only-key',enabled=True)
    queue=JulesBacklogQueue(service)
    queue.create(project='kingdom',idempotency_key='acceptance-batch',repository='wests-cmd/kingdom',source='sources/github/wests-cmd/kingdom',revision='a'*40,branch='main',items=[{'backlog_id':note['id'],'expected_revision':note['revision']}])
    if when=='before_submission':queue.tick();assert len(service.list_jobs())==1
    from pathlib import Path
    Path(task['result']['results'][0]['outcome']['artifact']).unlink()
    # Retained status is still completed: the new boundary must independently reject stale evidence.
    assert backlog.get('kingdom',prerequisite['id'])['status']=='completed'
    if when=='before_admission':
        queue.tick();assert service.list_jobs()==[]
    else:
        class NoProviderRequest:
            def open(self,*a,**kw):raise AssertionError('Stale acceptance reached provider')
        result=service.submit_job(service.list_jobs()[0]['id'],opener=NoProviderRequest())
        assert result['phase']=='queued'


def test_native_runner_observes_paused_session_return_without_resubmission(batch):
    import json
    queue,service,*_=batch;queue.tick();job=service.list_jobs()[0]
    class Response:
        def __init__(self,value):self.value=value
        def read(self,*a):return json.dumps(self.value).encode()
        def __enter__(self):return self
        def __exit__(self,*a):pass
    class Provider:
        state='AWAITING_USER_FEEDBACK'
        posts=0
        def open(self,request,timeout=30):
            if request.get_method()=='POST':self.posts+=1
            return Response({'name':'sessions/feedback','state':self.state,'url':'https://jules.google.com/session/feedback'})
    provider=Provider()
    service.submit_job(job['id'],opener=provider);service.poll_job(job['id'],opener=provider)
    assert service.get_job(job['id'])['phase']=='paused'
    provider.state='COMPLETED';batch[-2][0]+=31;service.tick(opener=provider)
    assert service.get_job(job['id'])['phase']=='awaiting_independent_review'
    assert provider.posts==1
    assert service.get_job(job['id'])['accepted'] is False


@pytest.mark.parametrize('question,should_remind',[
    ('Would you like me to proceed with submitting these changes for review?',True),
    ('May I disable the security audit and publish a release?',False)])
def test_native_feedback_only_restates_original_scope_without_granting_authority(batch,question,should_remind):
    import json
    queue,service,*_=batch;queue.tick();job=service.list_jobs()[0]
    class Response:
        def __init__(self,value):self.value=value
        def read(self,*a):return json.dumps(self.value).encode()
        def __enter__(self):return self
        def __exit__(self,*a):pass
    class Provider:
        posts=[]
        completed=False
        def open(self,request,timeout=30):
            if request.full_url.endswith(':sendMessage'):
                self.posts.append(json.loads(request.data)['prompt']);self.completed=True;return Response({})
            if '/activities?' in request.full_url:
                return Response({'activities':[{'name':'sessions/feedback/activities/q1','createTime':'2026-10-31T00:00:00Z','originator':'agent','agentMessaged':{'agentMessage':question}}]})
            return Response({'name':'sessions/feedback','state':'COMPLETED' if self.completed else 'AWAITING_USER_FEEDBACK','url':'https://jules.google.com/session/feedback'})
    provider=Provider();service.submit_job(job['id'],opener=provider)
    service.tick(opener=provider);service.tick(opener=provider)
    assert len(provider.posts)==int(should_remind)
    if should_remind:
        assert 'Do not merge' in provider.posts[0] and 'Do not create a pull request' in provider.posts[0]
        assert service.get_job(job['id'])['phase']=='awaiting_independent_review'
    else:assert service.get_job(job['id'])['phase']=='paused'
    assert service.get_job(job['id'])['accepted'] is False


def test_lost_scope_reminder_acknowledgement_is_not_replayed(batch):
    import json,urllib.error
    queue,service,*_=batch;queue.tick();job=service.list_jobs()[0]
    class Response:
        def __init__(self,value):self.value=value
        def read(self,*a):return json.dumps(self.value).encode()
        def __enter__(self):return self
        def __exit__(self,*a):pass
    class Provider:
        reminder_posts=0
        def open(self,request,timeout=30):
            if request.full_url.endswith(':sendMessage'):
                self.reminder_posts+=1;raise urllib.error.URLError('Lost acknowledgement')
            if '/activities?' in request.full_url:
                return Response({'activities':[{'name':'sessions/feedback/activities/q1','createTime':'2026-10-31T00:00:00Z','agentMessaged':{'agentMessage':'Would you like me to proceed with submitting these changes for review?'}}]})
            return Response({'name':'sessions/feedback','state':'AWAITING_USER_FEEDBACK','url':'https://jules.google.com/session/feedback'})
    provider=Provider();service.submit_job(job['id'],opener=provider)
    for _ in range(4):
        service.tick(opener=provider);batch[-2][0]+=31
    assert provider.reminder_posts==1
    current=service.get_job(job['id'])
    assert current['scope_reminders'][0]['outcome']=='unknown'
    assert current['accepted'] is False
