"""Crash-window recovery against persisted SQLite records; no inference or external actions."""
import asyncio
import json
import pytest
from test_request_bridge import _harness_fixture,body,setup
from backend.runtime.request_origin import request_origin
from backend.runtime.request_recovery import reconcile_interrupted_requests


def test_harness_crash_after_child_save_reattaches_without_replay(tmp_path,monkeypatch):
    service,harness,models,agents=_harness_fixture(tmp_path,monkeypatch)
    saved=service.create(dict(body(),mode="harness",harness_id="example",allow_process=True,prompt="literal"))
    running=service.update(saved["id"],{"status":"running","governed_submission_started":True})
    task=harness.submit("example",running["prompt"],running["project_scope"],expected_revision=running["harness_revision"],request_id=running["id"],origin=request_origin(running))
    before=service.engine.tasks.repo.get(task["id"])
    assert reconcile_interrupted_requests(service.db)=={"linked":1}
    recovered=service.get(saved["id"])
    assert recovered["governed_task_id"]==task["id"] and recovered["recovery_hold"]
    assert reconcile_interrupted_requests(service.db)=={}
    assert asyncio.run(service.run(saved["id"]))["recovery_hold"]
    assert service.engine.tasks.repo.get(task["id"])==before
    continued=asyncio.run(service.run(saved["id"],resume_recovered=True))
    assert continued["governed_task_id"]==task["id"] and not continued["recovery_hold"]
    assert len(service.engine.tasks.list())==1 and models.calls==agents.created==0


def test_no_child_and_multiple_children_are_held(tmp_path,monkeypatch):
    service,harness,models,agents=_harness_fixture(tmp_path,monkeypatch)
    for key in ("missing","duplicate"):
        saved=service.create(dict(body(),idempotency_key=key,mode="harness",harness_id="example",allow_process=True,prompt="literal"))
        running=service.update(saved["id"],{"status":"running","governed_submission_started":True})
        if key=="duplicate":
            for _ in range(2):
                harness.submit("example",running["prompt"],running["project_scope"],expected_revision=running["harness_revision"],request_id=running["id"],origin=request_origin(running))
    assert reconcile_interrupted_requests(service.db)=={"missing":1,"ambiguous":1}
    for item in service.list("chat","projects/a"):
        assert item["recovery_hold"] and not item.get("governed_task_id")
        with pytest.raises(ValueError):asyncio.run(service.run(item["id"],resume_recovered=True))
    assert len(service.engine.tasks.list())==2 and models.calls==agents.created==0


def test_interrupted_agent_recovers_exact_session_but_never_auto_runs(tmp_path,monkeypatch):
    service,models,agents=setup(tmp_path)
    saved=service.create(dict(body(),mode="agent"))
    running=service.update(saved["id"],{"status":"running","governed_submission_started":True})
    with service.db.get_connection() as conn:
        conn.execute("CREATE TABLE agent_sessions(id TEXT PRIMARY KEY,state_json TEXT NOT NULL)")
        conn.execute("INSERT INTO agent_sessions VALUES(?,?)",("child",json.dumps({"id":"child","workspace":running["project_scope"],"request_origin":request_origin(running),"status":"ready"})))
    assert reconcile_interrupted_requests(service.db)=={"linked":1}
    result=asyncio.run(service.run(saved["id"]))
    assert result["agent_session_id"]=="child" and result["recovery_hold"]
    assert models.calls==agents.created==agents.runs==0
    assert service.cancel(saved["id"])["status"]=="cancelled"
    assert agents.cancelled==["child"]


def test_stale_resume_cannot_acquire_a_changed_checkpoint(tmp_path):
    service,_,_=setup(tmp_path)
    saved=service.create(dict(body(),mode="agent"))
    changed=service.update(saved["id"],{"status":"waiting_review","recovery_hold":True})
    assert service.update(saved["id"],{"status":"running"},expected={"waiting_review"},expected_updated_at=saved["updated_at"]) is None
    assert service.get(saved["id"])==changed
