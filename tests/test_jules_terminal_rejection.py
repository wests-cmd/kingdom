"""Exact candidate rejection through real durable stores; provider HTTP only is substituted."""
import hashlib
import json
from types import SimpleNamespace

import pytest
from backend.integrations.jules import JulesService
from backend.runtime.work_backlog import WorkBacklog
from backend.storage.db import Database

PATCH='diff --git a/release-notes.md b/release-notes.md\nnew file mode 100644\n--- /dev/null\n+++ b/release-notes.md\n@@ -0,0 +1 @@\n+Unrelated generated notes\n'

class Provider:
    def __init__(self):self.calls=[];self.state='QUEUED';self.callback=None;self.response_changes={};self.activities=None;self.lose_ack=False
    def open(self,request,timeout=30):
        self.calls.append((request.get_method(),request.full_url,request.data))
        if self.callback:self.callback()
        if request.full_url.endswith(':sendMessage') and self.lose_ack:raise OSError('Injected lost acknowledgement')
        value=({'activities':[{'createTime':'2026-11-01T00:00:00Z','artifacts':[{'changeSet':{'source':'sources/github/wests-cmd/kingdom','gitPatch':{'baseCommitId':'a'*40,'unidiffPatch':PATCH}}}]}]} if '/activities?' in request.full_url else
               {'name':'sessions/reject-fixture','state':self.state,'sourceContext':{'source':'sources/github/wests-cmd/kingdom'}})
        if self.activities is not None and '/activities?' in request.full_url:value={'activities':self.activities}
        elif request.full_url.endswith(':sendMessage'):value={}
        else:value.update(self.response_changes)
        class Response:
            def read(self,*a):return json.dumps(value).encode()
            def __enter__(self):return self
            def __exit__(self,*a):pass
        return Response()

def build_candidate(tmp_path,unknown_reminder=False):
    now=[1000.0];level=[5];events=[]
    db=Database(tmp_path/'state.db')
    engine=SimpleNamespace(execution_policy=SimpleNamespace(get=lambda:{'level':level[0]}),events=SimpleNamespace(publish=lambda *a:events.append(a)))
    service=JulesService(db,engine=engine,secrets_root=tmp_path/'secrets',clock=lambda:now[0])
    service.configure(api_key='private-test-key',enabled=True)
    backlog=WorkBacklog(db,engine)
    note=backlog.register('kingdom','fix',title='Fix backlog processing',description='Implement tested backlog processing')
    job=service.register_job('kingdom',note['id'],'job','sources/github/wests-cmd/kingdom','wests-cmd/kingdom','a'*40,'main','Fix backlog processing',deadline_seconds=3600)
    provider=Provider();service.submit_job(job['id'],opener=provider)
    if unknown_reminder:
        from backend.integrations.jules_feedback import remind_original_scope,QUESTION
        provider.state='AWAITING_USER_FEEDBACK';service.poll_job(job['id'],opener=provider)
        provider.activities=[{'name':'sessions/reject-fixture/activities/question','createTime':'2026-11-01T00:00:00Z','agentMessaged':{'agentMessage':QUESTION}}]
        provider.lose_ack=True;remind_original_scope(service,job['id'],opener=provider)
        provider.lose_ack=False;provider.activities=None
        now[0]+=31
    provider.state='COMPLETED'
    service.poll_job(job['id'],opener=provider);job=service.fetch_candidate(job['id'],opener=provider)
    binding=dict(job_id=job['id'],project=job['project'],backlog_id=job['backlog_id'],repository=job['repository'],source=job['source'],base_revision=job['revision'],branch=job['branch'],session=job['session'],patch_sha256=job['candidate']['patch_sha256'])
    request=dict(expected_job_binding=binding,expected_record_version=job['record_version'],reason='outcome_not_implemented')
    provider.calls.clear()
    return service,provider,backlog,note,job,request,now,level,events


@pytest.fixture
def candidate(tmp_path):return build_candidate(tmp_path)

def test_exact_owner_rejection_observes_terminal_without_accepting_or_renewing(candidate):
    service,provider,backlog,note,job,request,now,level,events=candidate
    now[0]=job['deadline_at']+100;level[0]=0
    rejected=service.reject_candidate(job['id'],**request,opener=provider)
    assert rejected['phase']=='rejected' and rejected['accepted'] is False
    assert rejected['deadline_at']==job['deadline_at'] and rejected['repair_attempts']==0
    assert len(provider.calls)==1 and provider.calls[0][0]=='GET' and provider.calls[0][2] is None
    assert rejected['rejection']['binding']==request['expected_job_binding']
    assert rejected['rejection']['provider_observation']['state']=='COMPLETED'
    assert backlog.get('kingdom',note['id'])['status']=='needs_planning'
    assert service.reject_candidate(job['id'],**request,opener=provider)==rejected
    assert len(provider.calls)==1
    assert any(name=='jules.candidate_rejected' for name,payload in events)
    assert any(name=='jules.job_changed' and payload.get('phase')=='rejected' for name,payload in events)


@pytest.mark.parametrize('changes',[{'state':'IN_PROGRESS'},{'state':'QUEUED'},{'state':'FAILED'},{'state':'UNRECOGNIZED'},{'name':'sessions/other'},{'sourceContext':{'source':'sources/github/other/repo'}},{'sourceContext':{}},{'sourceContext':[]}])
def test_active_unknown_or_mismatched_provider_cannot_release_candidate(candidate,changes):
    service,provider,backlog,note,job,request,*_=candidate
    provider.response_changes=changes
    with pytest.raises(ValueError):service.reject_candidate(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job
    from backend.integrations.jules_backlog import JulesBacklogQueue
    assert JulesBacklogQueue(service).occupies_slot(job) is True


def test_wrong_exact_binding_stale_request_or_revocation_makes_no_provider_call(candidate):
    service,provider,backlog,note,job,request,*_=candidate
    for key,bad in [('job_id','jules-111111111111'),('patch_sha256','b'*64),('backlog_id','other'),('base_revision','b'*40),('source','sources/github/other/repo'),('session','sessions/other')]:
        with pytest.raises(ValueError):service.reject_candidate(job['id'],**{**request,'expected_job_binding':{**request['expected_job_binding'],key:bad}},opener=provider)
    with pytest.raises(ValueError):service.reject_candidate(job['id'],**{**request,'expected_record_version':job['record_version']-1},opener=provider)
    service.configure(enabled=False)
    with pytest.raises(ValueError):service.reject_candidate(job['id'],**request,opener=provider)
    assert provider.calls==[] and service.get_job(job['id'])==job


def test_cancellation_during_provider_observation_is_not_overwritten(candidate):
    service,provider,backlog,note,job,request,*_=candidate
    provider.callback=lambda:service.cancel_job(job['id'],'Owner stopped while observing')
    with pytest.raises(ValueError):service.reject_candidate(job['id'],**request,opener=provider)
    current=service.get_job(job['id']);assert current['phase']=='cancelled' and 'rejection' not in current


def test_unknown_earlier_outbound_message_cannot_be_assumed_stopped(tmp_path):
    service,provider,backlog,note,job,request,*_=build_candidate(tmp_path,unknown_reminder=True)
    assert job['scope_reminders'][0]['outcome']=='unknown'
    with pytest.raises(ValueError):service.reject_candidate(job['id'],**request,opener=provider)
    assert provider.calls==[]
    assert service.get_job(job['id'])==job


def test_rejected_terminal_job_releases_only_unrelated_admission(candidate):
    from backend.integrations.jules_backlog import JulesBacklogQueue
    service,provider,backlog,note,job,request,*_=candidate
    dependent=backlog.register('kingdom','dependent',title='Depends on actual accepted work',depends_on=[note['id']])
    independent=backlog.register('kingdom','independent',title='Independent work')
    queue=JulesBacklogQueue(service)
    queue.create(project='kingdom',idempotency_key='next',repository=job['repository'],source=job['source'],revision=job['revision'],branch=job['branch'],
        items=[{'backlog_id':r['id'],'expected_revision':r['revision']} for r in (dependent,independent)],deadline_seconds=3600)
    queue.tick();assert len(service.list_jobs())==1
    rejected=service.reject_candidate(job['id'],**request,opener=provider)
    assert queue.occupies_slot(rejected) is False
    queue.tick()
    assert {j['backlog_id'] for j in service.list_jobs()}=={note['id'],independent['id']}
    assert backlog.get('kingdom',note['id'])['status']=='needs_planning'
    assert backlog.get('kingdom',dependent['id'])['status']=='needs_planning'
    assert service.cancel_job(job['id'])['phase']=='rejected'
    assert service.run_job(job['id'],opener=provider)['phase']=='rejected'


def test_owner_http_endpoint_is_strict_and_never_publishes_provider_text(candidate,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.integrations import jules_api
    from backend.security.http_auth import owner_auth
    service,provider,backlog,note,job,request,*_=candidate
    service.opener=provider
    monkeypatch.setattr(jules_api,'service',lambda:service)
    app=FastAPI();app.include_router(jules_api.router);client=TestClient(app)
    path='/integrations/jules/jobs/'+job['id']+'/reject-candidate'
    assert client.post(path,json=request).status_code==403
    assert client.post(path,json=request,headers={'X-Kingdom-Request':'1'}).status_code==401
    headers={'Authorization':'Bearer '+owner_auth.token,'X-Kingdom-Request':'1'}
    assert client.post(path,json={**request,'accepted':True},headers=headers).status_code==422
    assert client.post(path,json=request,headers={**headers,'Origin':'https://untrusted.example'}).status_code==403
    assert provider.calls==[]
    provider.response_changes={'private_provider_field':'private-test-key is not audit data'}
    response=client.post(path,json=request,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['phase']=='rejected' and response.json()['accepted'] is False
    assert set(response.json())=={'id','phase','accepted','record_version','deadline_at','rejection'}
    assert 'prompt' not in response.json() and 'session_url' not in response.json()
    assert response.json()['rejection']['binding']==request['expected_job_binding']
    schema=client.get('/openapi.json').json()
    assert schema['paths'][path.replace(job['id'],'{job_id}')]['post']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/RejectionResponse')
    assert 'private_provider_field' not in response.text and 'private-test-key' not in response.text


def test_cancelled_candidate_requires_fresh_terminal_observation_before_reconciliation(candidate):
    service,provider,backlog,note,job,request,*_=candidate
    cancelled=service.cancel_job(job['id'],'Stop this unrelated patch')
    from backend.integrations.jules_backlog import JulesBacklogQueue
    assert JulesBacklogQueue(service).occupies_slot(cancelled) is True
    updated={**request,'expected_record_version':cancelled['record_version']}
    rejected=service.reject_candidate(job['id'],**updated,opener=provider)
    assert rejected['phase']=='rejected'
    assert JulesBacklogQueue(service).occupies_slot(rejected) is False
    assert len(provider.calls)==1 and provider.calls[0][0]=='GET'


def test_concurrent_observers_commit_one_rejection_record(candidate):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    service,provider,backlog,note,job,request,now,level,events=candidate
    other=JulesService(service.db,engine=service.engine,secrets_root=service.secrets_root,clock=service.clock)
    barrier=threading.Barrier(2);provider.callback=lambda:barrier.wait(timeout=3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda s:s.reject_candidate(job['id'],**request,opener=provider),(service,other)))
    assert results[0]==results[1]
    assert len([e for e in events if e[0]=='jules.candidate_rejected'])==1
    assert service.get_job(job['id'])['phase']=='rejected'


def test_crash_before_rejection_commit_preserves_original_job_and_slot(candidate,monkeypatch):
    service,provider,backlog,note,job,request,*_=candidate
    save=service._save_job
    def crash(conn,state):
        save(conn,state)
        raise RuntimeError('Injected crash before atomic commit')
    monkeypatch.setattr(service,'_save_job',crash)
    with pytest.raises(RuntimeError):service.reject_candidate(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job
    monkeypatch.setattr(service,'_save_job',save)
    assert service.reject_candidate(job['id'],**request,opener=provider)['phase']=='rejected'


def test_corrupted_retained_patch_cannot_be_rejected_under_original_digest(candidate):
    service,provider,backlog,note,job,request,*_=candidate
    # Deliberate durable-storage corruption; no production behavior is replaced.
    with service.db.get_connection() as conn:
        conn.execute('UPDATE jules_candidate_patches SET patch=? WHERE job_id=?',(PATCH+'tampered',job['id']));conn.commit()
    with pytest.raises(ValueError):service.reject_candidate(job['id'],**request,opener=provider)
    assert provider.calls==[] and service.get_job(job['id'])==job


def test_stale_runtime_expiry_cannot_overwrite_committed_rejection(candidate):
    service,provider,backlog,note,job,request,now,level,events=candidate
    now[0]=job['deadline_at']+100
    original_clock=service.clock
    fired=[False]
    def clock():
        if not fired[0]:
            fired[0]=True
            service.reject_candidate(job['id'],**request,opener=provider)
        return original_clock()
    service.clock=clock
    assert service.run_job(job['id'],opener=provider)['phase']=='rejected'
    assert service.get_job(job['id'])['phase']=='rejected'


def test_counterfeit_rejection_without_durable_audit_cannot_release_slot(candidate):
    from backend.integrations.jules_backlog import JulesBacklogQueue
    from backend.integrations.jules_rejection import FORMAT
    service,provider,backlog,note,job,request,*_=candidate
    counterfeit={**job,'phase':'rejected','accepted':False,'rejection':{
        'format':FORMAT,'reason':request['reason'],'binding':request['expected_job_binding'],
        'provider_observation':{'state':'COMPLETED','session':job['session'],'source':job['source']}}}
    assert JulesBacklogQueue(service).occupies_slot(counterfeit) is True


def test_provider_observation_failure_is_retryable_read_only_and_commits_nothing(candidate):
    service,provider,backlog,note,job,request,*_=candidate
    def fail():raise OSError('Injected provider read timeout')
    provider.callback=fail
    with pytest.raises(OSError):service.reject_candidate(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job
    provider.callback=None
    assert service.reject_candidate(job['id'],**request,opener=provider)['phase']=='rejected'
    assert all(method=='GET' and data is None for method,url,data in provider.calls)
