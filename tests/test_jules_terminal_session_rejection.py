from test_jules_terminal_rejection import build_candidate
from backend.integrations.jules_backlog import JulesBacklogQueue


def session_fixture(tmp_path):
    values=build_candidate(tmp_path)
    service,provider,backlog,note,job,request,now,level,events=values
    # Represent expiry before candidate fetch; retain all genuine provider/job bindings.
    with service.db.get_connection() as conn:
        job.pop('candidate',None)
        job['phase']='expired_remote_may_continue'
        service._save_job(conn,job);conn.commit()
    job=service.get_job(job['id'])
    request['expected_job_binding'].pop('patch_sha256')
    request['expected_record_version']=job['record_version']
    provider.activities=[]
    now[0]=job['deadline_at']+10
    return values[:4]+(job,request,now,level,events)


def test_expired_no_artifact_closure_releases_slot_without_acceptance(tmp_path):
    service,provider,backlog,note,job,request,now,level,events=session_fixture(tmp_path)
    level[0]=0
    result=service.reject_terminal_session(job['id'],**request,opener=provider)
    assert result['phase']=='rejected' and result['accepted'] is False
    assert result['deadline_at']==job['deadline_at']
    assert result['session_rejection']['artifacts']==[]
    assert result['session_rejection']['artifact_status']=='none_observed'
    assert not JulesBacklogQueue(service).occupies_slot(result)
    assert backlog.get('kingdom',note['id'])['status']=='needs_planning'
    assert len(provider.calls)==3
    assert all(method=='GET' and body is None for method,url,body in provider.calls)
    assert service.reject_terminal_session(job['id'],**request,opener=provider)==result
    assert len(provider.calls)==3
import hashlib
import pytest
from backend.integrations.jules import JulesService
from test_jules_terminal_rejection import PATCH


def test_wrong_base_observed_directly_and_restart_validates_audit(tmp_path):
    service,provider,backlog,note,job,request,*_=session_fixture(tmp_path)
    provider.activities=[{'artifacts':[{'changeSet':{'source':job['source'],'gitPatch':{'baseCommitId':'b'*40,'unidiffPatch':PATCH}}}]}]
    result=service.reject_terminal_session(job['id'],**request,opener=provider)
    artifact=result['session_rejection']['artifacts'][0]
    assert artifact['base_revision']=='b'*40
    assert artifact['patch_sha256']==hashlib.sha256(PATCH.encode()).hexdigest()
    assert 'candidate' not in result and result['accepted'] is False
    restarted=JulesService(service.db,engine=service.engine,secrets_root=service.secrets_root,clock=service.clock)
    assert not JulesBacklogQueue(restarted).occupies_slot(restarted.get_job(job['id']))
    counterfeit={**result,'session_rejection':{**result['session_rejection'],'reason':'owner_rejected'}}
    assert JulesBacklogQueue(restarted).occupies_slot(counterfeit)
    assert service.cancel_job(job['id'])['phase']=='rejected'
    assert service.run_job(job['id'],opener=provider)['phase']=='rejected'


@pytest.mark.parametrize('change',[{'state':'IN_PROGRESS'},{'state':'FAILED'},{'state':'UNKNOWN'},{'name':'sessions/other'},{'sourceContext':{}},{'sourceContext':[]}])
def test_invalid_terminal_observation_leaves_slot(tmp_path,change):
    service,provider,backlog,note,job,request,*_=session_fixture(tmp_path)
    provider.response_changes=change
    with pytest.raises(ValueError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job and JulesBacklogQueue(service).occupies_slot(job)


@pytest.mark.parametrize('activity',[
    {'artifacts':[{'changeSet':{'source':'sources/github/other/repo','gitPatch':{}}}]},
    {'artifacts':[{'changeSet':{'source':'sources/github/wests-cmd/kingdom','gitPatch':{'baseCommitId':'bad','unidiffPatch':PATCH}}}]},
    {'artifacts':[{'changeSet':{'source':'sources/github/wests-cmd/kingdom','gitPatch':{'baseCommitId':'a'*40}}}]},
    {'artifacts':{}}, {'artifacts':[{'unknownArtifact':{}}]},
])
def test_malformed_or_ambiguous_artifact_does_not_mean_no_artifact(tmp_path,activity):
    service,provider,backlog,note,job,request,*_=session_fixture(tmp_path)
    provider.activities=[activity]
    with pytest.raises(ValueError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job


def test_revalidate_terminal_at_end_and_cancellation_version(tmp_path):
    service,provider,backlog,note,job,request,*_=session_fixture(tmp_path)
    def change_on_final():
        if len(provider.calls)==3:provider.state='IN_PROGRESS'
    provider.callback=change_on_final
    with pytest.raises(ValueError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job
    provider.state='COMPLETED';provider.calls.clear()
    provider.callback=lambda:service.cancel_job(job['id']) if len(provider.calls)==2 else None
    with pytest.raises(ValueError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])['phase']=='cancelled'


def test_uncertain_outbound_and_revocation_never_observe(tmp_path):
    service,provider,backlog,note,job,request,*_=session_fixture(tmp_path)
    with service.db.get_connection() as conn:
        job['scope_reminders']=[{'outcome':'unknown'}];service._save_job(conn,job);conn.commit()
    request['expected_record_version']=service.get_job(job['id'])['record_version']
    with pytest.raises(ValueError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert provider.calls==[]


def test_http_auth_typed_bounded_response_and_no_caller_digest(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.integrations import jules_api
    from backend.security.http_auth import owner_auth
    service,provider,backlog,note,job,request,*_=session_fixture(tmp_path)
    service.opener=provider;monkeypatch.setattr(jules_api,'service',lambda:service)
    app=FastAPI();app.include_router(jules_api.router);client=TestClient(app)
    path='/integrations/jules/jobs/'+job['id']+'/reject-terminal-session'
    assert client.post(path,json=request).status_code==403
    assert client.post(path,json=request,headers={'X-Kingdom-Request':'1'}).status_code==401
    headers={'Authorization':'Bearer '+owner_auth.token,'X-Kingdom-Request':'1'}
    bad={**request,'expected_job_binding':{**request['expected_job_binding'],'patch_sha256':'c'*64}}
    assert client.post(path,json=bad,headers=headers).status_code==422
    provider.response_changes={'secret_private_text':'private-test-key'}
    response=client.post(path,json=request,headers=headers)
    assert response.status_code==200,response.text
    assert set(response.json())=={'id','phase','accepted','record_version','deadline_at','session_rejection'}
    assert 'secret_private_text' not in response.text and 'private-test-key' not in response.text


def test_concurrent_observers_and_atomic_rollback(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    service,provider,backlog,note,job,request,now,level,events=session_fixture(tmp_path)
    original=service._save_job
    def fail(conn,value):
        original(conn,value);raise RuntimeError('crash before commit')
    monkeypatch.setattr(service,'_save_job',fail)
    with pytest.raises(RuntimeError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job
    monkeypatch.setattr(service,'_save_job',original)
    other=JulesService(service.db,engine=service.engine,secrets_root=service.secrets_root,clock=service.clock)
    barrier=threading.Barrier(2);provider.callback=lambda:barrier.wait(timeout=3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda s:s.reject_terminal_session(job['id'],**request,opener=provider),(service,other)))
    assert results[0]==results[1]
    assert len([e for e in events if e[0]=='jules.session_rejected'])==1

def test_provider_timeout_and_repeated_pagination_fail_closed(tmp_path):
    service,provider,backlog,note,job,request,*_=session_fixture(tmp_path)
    def fail():raise OSError('GET timeout')
    provider.callback=fail
    with pytest.raises(OSError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job
    provider.callback=None
    underlying=provider.open
    def repeated(req,timeout=30):
        if '/activities?' not in req.full_url:return underlying(req,timeout)
        import json
        class Response:
            def read(self,*a):return json.dumps({'activities':[],'nextPageToken':'again'}).encode()
            def __enter__(self):return self
            def __exit__(self,*a):pass
        return Response()
    provider.open=repeated
    with pytest.raises(ValueError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job


def test_negative_session_closure_advances_only_unrelated_work(tmp_path):
    service,provider,backlog,note,job,request,now,*_=session_fixture(tmp_path)
    # New batch has its own owner-approved window; rejection never renews the old job.
    dependent=backlog.register('kingdom','dependent',title='Depends on accepted work',depends_on=[note['id']])
    independent=backlog.register('kingdom','independent',title='Independent work')
    queue=JulesBacklogQueue(service)
    queue.create(project='kingdom',idempotency_key='next',repository=job['repository'],source=job['source'],revision=job['revision'],branch=job['branch'],
        items=[{'backlog_id':r['id'],'expected_revision':r['revision']} for r in (dependent,independent)],deadline_seconds=3600)
    queue.tick();assert len(service.list_jobs())==1
    service.reject_terminal_session(job['id'],**request,opener=provider)
    queue.tick()
    assert {j['backlog_id'] for j in service.list_jobs()}=={note['id'],independent['id']}
    assert backlog.get('kingdom',dependent['id'])['status']=='needs_planning'


def test_observation_authority_revoked_during_get_cannot_close(tmp_path):
    service,provider,backlog,note,job,request,*_=session_fixture(tmp_path)
    provider.callback=lambda:service.configure(enabled=False) if len(provider.calls)==2 else None
    with pytest.raises(ValueError):service.reject_terminal_session(job['id'],**request,opener=provider)
    assert service.get_job(job['id'])==job
