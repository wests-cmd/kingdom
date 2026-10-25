import json
from types import SimpleNamespace
import pytest
from backend.storage.db import Database
from backend.runtime.problem_bot import ProblemBot
from backend.runtime.work_backlog import WorkBacklog

@pytest.fixture
def rig(tmp_path):
    events=[]
    bus=SimpleNamespace(publish=lambda *a,**k:events.append((a,k)))
    db=Database(tmp_path/'problems.db')
    backlog=WorkBacklog(db,SimpleNamespace(events=bus))
    states=[{'id':'programme1','project':'kingdom','sections':[{'items':[{'key':'s1-t1','planning':'blocked','work_status':'needs_planning',
              'blocked_reasons':['api_key=secret raw provider response']}],
              'integration':{'key':'s1-integration','planning':'unplanned','work_status':'needs_planning'}}]}]
    programmes=SimpleNamespace(list=lambda:states,snapshot=lambda ident:next(s for s in states if s['id']==ident))
    bot=ProblemBot(db,programmes,backlog,bus)
    return bot,backlog,states,events

def test_real_checkpoint_routes_one_disabled_repair_note_and_no_secret(rig):
    bot,backlog,_,events=rig
    bot.tick();bot.tick()
    incidents=bot.listing();work=backlog.list()
    assert len(incidents)==len(work)==1
    assert incidents[0]['assigned_role']=='planner'
    assert work[0]['status']=='needs_planning' and work[0]['enabled'] is False
    assert work[0]['intent']['mission_id'] is None
    assert 'secret' not in json.dumps([incidents,work,events])

def test_crash_between_register_and_checkpoint_reuses_work(rig,monkeypatch):
    bot,backlog,_,_=rig
    original=bot._save
    monkeypatch.setattr(bot,'_save',lambda value:(_ for _ in ()).throw(RuntimeError('crash')))
    with pytest.raises(RuntimeError):bot.tick()
    monkeypatch.setattr(bot,'_save',original)
    restarted=ProblemBot(bot.db,bot.programmes,backlog,bot.events)
    restarted.tick()
    assert len(backlog.list())==1 and restarted.listing()[0]['work_id']==backlog.list()[0]['id']

def test_model_retry_is_not_resolution_but_verified_checkpoint_is(rig):
    bot,_,states,_=rig;bot.tick()
    row=states[0]['sections'][0]['items'][0]
    row['planning']='planning';bot.tick()
    assert bot.listing()[0]['status']=='open'
    row.update(planning='reviewed',work_status='completed');bot.tick()
    assert bot.listing()[0]['status']=='resolved'

def test_transient_connection_routes_to_connection_diagnosis(rig):
    bot,_,states,_=rig
    states[0]['sections'][0]['items'][0]['planning_failure']={'retryable':True}
    bot.tick()
    assert bot.listing()[0]['assigned_role']=='researcher'

def test_fixed_metric_labels_and_unknown_categories_rejected(rig):
    bot,_,_,_=rig;bot.tick()
    snapshot=bot.snapshot()
    assert set(snapshot['open_by_category'])=={'planning_contract','planning_transport','execution_review','runner_error'}
    assert snapshot['reliability_target']['measured'] is False
    with pytest.raises(ValueError):bot.observe('programme','p1','grant_admin')

def test_incident_capacity_is_bounded(rig):
    bot,_,_,_=rig
    sample=bot.observe('runtime','failure0','runner_error')
    with bot.db.get_connection() as conn:
        for i in range(1,200):
            conn.execute('INSERT INTO problem_incidents VALUES(?,?)',(str(i),json.dumps({**sample,'id':str(i)})))
        conn.commit()
    assert bot.observe('runtime','overflow','runner_error') is None
    assert len(bot.listing())==200 and bot.snapshot()['capacity_reached'] is True

def test_problem_status_requires_owner(rig,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.runtime import problem_api
    monkeypatch.setattr(problem_api,'_service',rig[0])
    app=FastAPI();app.include_router(problem_api.router)
    assert TestClient(app).get('/problems').status_code in {401,403}
