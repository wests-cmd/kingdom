import asyncio
from types import SimpleNamespace
import pytest
from backend.runtime.orchestration_api import job_view
from backend.runtime.background_requests import BackgroundRequests


def test_unassigned_request_does_not_claim_unrelated_tool_execution():
    view=job_view({'id':'request','status':'queued'}, tasks=[{'assigned_knight':'other','metadata':{},'result':{'verification':{'state':'VERIFIED'}}}])
    assert view['verified_tools']==0 and view['assigned_workers']==[]


def test_actual_worker_and_error_survive_summary_without_transcript():
    view=job_view({'id':'request','agent_session_id':'agent','status':'waiting_review'},
                  {'status':'needs_review','error':'Missing filesystem grant','messages':[{'content':'secret prompt'}]},
                  [{'assigned_knight':'researcher','metadata':{'agent_session_id':'agent'},'result':{'results':[{'verification':{'state':'VERIFIED'}}]}}])
    assert view['assigned_workers']==['researcher'] and view['verified_tools']==1
    assert view['reason']=='Missing filesystem grant'
    assert 'secret prompt' not in str(view)


def test_background_rejects_review_needed_work_without_retry():
    runner=BackgroundRequests(lambda:SimpleNamespace(get=lambda ident:{'status':'waiting_review'}))
    with pytest.raises(ValueError):runner.start('blocked')
    assert not runner.active


def test_verified_local_executor_is_visible_and_interrupted_agent_is_not_thinking():
    task={'metadata':{'agent_session_id':'agent'},'result':{'results':[{'knight':'researcher','verification':{'state':'VERIFIED'}},{'knight':'untrusted','verification':{'state':'UNVERIFIED'}}]}}
    view=job_view({'id':'request','agent_session_id':'agent','status':'waiting_review'},{'status':'thinking'},[task])
    assert view['assigned_workers']==['researcher']
    assert view['display_status']=='waiting_review'


def test_browser_independent_work_is_bounded_and_single_slot():
    async def scenario():
        entered=asyncio.Event();release=asyncio.Event();calls=[]
        async def run(ident):calls.append(ident);entered.set();await release.wait()
        service=SimpleNamespace(get=lambda ident:{'status':'queued'},update=lambda *a,**kw:None,run=run)
        runner=BackgroundRequests(lambda:service)
        assert runner.start('one')['active_request_ids']==['one']
        await entered.wait()
        with pytest.raises(ValueError):runner.start('two')
        assert runner.start('one')['active_request_ids']==['one']
        release.set();await asyncio.gather(*runner.active.values())
        assert calls==['one'] and not runner.active
    asyncio.run(scenario())


def test_shutdown_checkpoints_running_work_for_review():
    async def scenario():
        entered=asyncio.Event();updates=[]
        async def run(ident):entered.set();await asyncio.Event().wait()
        service=SimpleNamespace(get=lambda ident:{'status':'queued'},update=lambda ident,change,**kw:updates.append(change),run=run)
        runner=BackgroundRequests(lambda:service);runner.start('one');await entered.wait();await runner.stop()
        assert updates[-1]['status']=='waiting_review' and not runner.active
    asyncio.run(scenario())
