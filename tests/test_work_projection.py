"""Actual SQLite snapshot and HTTP authorization tests, not model inference."""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.storage.db import Database
from backend.runtime.work_projection import project_work
from backend.runtime.work_api import router
from backend.security.http_auth import owner_auth


@pytest.fixture
def database(tmp_path):
    db=Database(tmp_path/"work.db")
    with db.get_connection() as conn:
        conn.execute("CREATE TABLE conversation_requests(id TEXT PRIMARY KEY,session_scope TEXT,project_scope TEXT,idem TEXT,state_json TEXT)")
        for table in ("missions","agent_sessions"):
            conn.execute(f"CREATE TABLE {table}(id TEXT PRIMARY KEY,state_json TEXT)")
    return db


def save(db,kind,ident,**state):
    data={"id":ident,"status":"queued","created_at":1,**state}
    with db.get_connection() as conn:
        if kind=="request":
            conn.execute("INSERT INTO conversation_requests VALUES(?,?,?,?,?)",(ident,data["session_scope"],data["project_scope"],ident,json.dumps(data)))
        elif kind=="task":
            conn.execute("INSERT INTO tasks(id,type,status,created_at,updated_at,metadata_json,result_json,prompt) VALUES(?,?,?,?,?,?,?,?)",
                (ident,"fixture",data["status"],1,data.get("updated_at",1),json.dumps(data.get("metadata",{})),json.dumps(data.get("result")),"PRIVATE-PROMPT"))
        else:
            table={"mission":"missions","agent":"agent_sessions"}[kind]
            conn.execute(f"INSERT INTO {table} VALUES(?,?)",(ident,json.dumps(data)))


def test_one_root_with_linked_mission_and_task(database):
    save(database,"request","r",project_scope="a",session_scope="s",governed_mission_id="m",status="waiting_review",prompt="PRIVATE-OBJECTIVE")
    save(database,"mission","m",version=2,status="running",steps={"step":{"task_id":"t"}},plan={"objective":"PRIVATE-PLAN"})
    save(database,"task","t",status="completed",metadata={"mission_id":"m","mission_version":2,"step_id":"step"},
         result={"results":[{"verification":{"state":"VERIFIED"},"outcome":{"output":"PRIVATE-OUTPUT"}}]})
    snapshot=project_work(database)
    assert snapshot["complete_snapshot"] and snapshot["root_counts"]=={"attention":1}
    root=snapshot["items"][0]
    assert root["status"]=="waiting_review"
    assert root["children"][0]["status"]=="running"
    assert root["children"][0]["children"][0]["evidence"]=="retained_controller_receipt"
    assert "PRIVATE-" not in json.dumps(snapshot)
    scoped=project_work(database,project_scope="a",session_scope="s")
    assert scoped["items"][0]["children"]==[] and scoped["items"][0]["unresolved_links"]==1


def test_exact_scope_and_reciprocal_links(database):
    save(database,"request","r",project_scope="a",session_scope="s",governed_task_id="t")
    save(database,"request","other",project_scope="ab",session_scope="s",governed_task_id="x")
    save(database,"request","different-session",project_scope="a",session_scope="ss")
    save(database,"task","t",status="completed",metadata={"project_scope":"a","conversation_request_id":"r"})
    save(database,"task","x",metadata={"project_scope":"ab","conversation_request_id":"other"})
    save(database,"task","fake",metadata={"project_scope":"a","conversation_request_id":"r"})
    scoped=project_work(database,project_scope="a",session_scope="s")
    assert [r["id"] for r in scoped["items"]]==["r"]
    assert [r["id"] for r in scoped["items"][0]["children"]]==["t"]
    assert scoped["items"][0]["children"][0]["evidence"]=="recorded_only"
    assert "fake" not in json.dumps(scoped)
    assert any(r["id"]=="fake" for r in project_work(database)["items"])
    with pytest.raises(ValueError):project_work(database,project_scope="a")


def test_conflicting_parents_and_unknown_status_are_not_hidden(database):
    for ident in ("r1","r2"):
        save(database,"request",ident,project_scope="a",session_scope=ident,agent_session_id="agent")
    save(database,"agent","agent",workspace="a",status="arbitrary-provider-status",pending=[])
    snapshot=project_work(database)
    assert len(snapshot["items"])==3
    assert next(x for x in snapshot["items"] if x["id"]=="agent")["status"]=="unknown"
    assert all(x["unresolved_links"]==1 for x in snapshot["items"] if x["kind"]=="request")


def test_bounded_snapshot_and_missing_link_fail_visibly(database):
    save(database,"request","old",project_scope="a",session_scope="s")
    save(database,"request","new",project_scope="a",session_scope="s",governed_task_id="missing")
    snapshot=project_work(database,limit=1)
    assert not snapshot["complete_snapshot"] and "request" in snapshot["truncated_sources"]
    assert snapshot["items"][0]["unresolved_links"]==1


def test_projection_no_writes_and_owner_boundary(database,monkeypatch):
    monkeypatch.setattr("backend.storage.db.db",database)
    save(database,"task","t",status="queued")
    app=FastAPI();app.include_router(router)
    client=TestClient(app)
    assert client.get("/work/overview").status_code==401
    auth={"Authorization":"Bearer "+owner_auth.token}
    assert client.get("/work/overview",headers=auth).status_code==200
    assert client.get("/work/overview?project_scope=a",headers=auth).status_code==400
    assert client.post("/work/overview",headers=auth).status_code==405
    with database.get_connection() as conn:
        assert conn.execute("SELECT status FROM tasks WHERE id='t'").fetchone()[0]=="queued"


def test_missing_lazy_tables_are_empty_not_created(tmp_path):
    db=Database(tmp_path/"empty.db")
    assert project_work(db)["items"]==[]
    with db.get_connection() as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='conversation_requests'").fetchone() is None
