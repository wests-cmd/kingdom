"""Startup-only reconciliation of interrupted request admissions.

Read existing children and restore linkage; never execute, approve, cancel,
retry, create a child, change leases, or classify an effect as successful.
Run before the controller starts its scheduler and request runners.
"""
import json
import time
from backend.runtime.request_origin import request_origin

CHILDREN={"agent":("agent_sessions","agent_session_id"),
          "commander":("missions","governed_mission_id"),
          "harness":("tasks","governed_task_id"),
          "delegate":("tasks","governed_task_id")}


def find_child(conn,state):
    route=state.get("route")
    if route not in CHILDREN:
        return "no_child_route",None,None
    table,field=CHILDREN[route]
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
        return "missing",field,None
    ident=state["id"]
    if table=="tasks":
        rows=conn.execute("""SELECT id,prompt,metadata_json FROM tasks
            WHERE CASE WHEN json_valid(metadata_json) THEN
            json_extract(metadata_json,'$.conversation_request_id')=? OR
            json_extract(metadata_json,'$.request_origin.request_id')=? ELSE 0 END
            ORDER BY id LIMIT 2""",(ident,ident)).fetchall()
    else:
        rows=conn.execute(f"""SELECT id,state_json FROM {table}
            WHERE CASE WHEN json_valid(state_json) THEN
            json_extract(state_json,'$.request_origin.request_id')=? ELSE 0 END
            ORDER BY id LIMIT 2""",(ident,)).fetchall()
    if len(rows)!=1:
        return ("ambiguous" if rows else "missing"),field,None
    row=rows[0]
    if state.get(field) and state[field]!=row["id"]:
        return "conflicting",field,None
    if table=="tasks":
        meta=json.loads(row["metadata_json"])
        valid=(meta.get("request_origin")==request_origin(state)
               and meta.get("conversation_request_id")==ident
               and meta.get("project_scope")==state["project_scope"]
               and row["prompt"]==state["prompt"])
        if route=="harness":
            valid=valid and meta.get("tool")=="harness.run@1.0.0" and meta.get("harness_id")==state.get("harness_id") and meta.get("harness_revision")==state.get("harness_revision")
        else:
            valid=valid and meta.get("tool")=="text.analyze@1.0.0" and meta.get("group_id")==state.get("group_id") and meta.get("assigned_knight")==state.get("target_knight")
    else:
        child=json.loads(row["state_json"])
        valid=child.get("id")==row["id"] and child.get("request_origin")==request_origin(state)
        if route=="agent":
            valid=valid and child.get("workspace")==state["project_scope"]
        else:
            valid=valid and child.get("group_id")==state.get("group_id")
    return ("linked",field,row["id"]) if valid else ("conflicting",field,None)


def reconcile_interrupted_requests(database):
    """Idempotent, batched startup transition; no task states are written."""
    counts={}
    while True:
        with database.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversation_requests'").fetchone():
                return counts
            rows=conn.execute("""SELECT id,project_scope,session_scope,state_json FROM conversation_requests
                WHERE CASE WHEN json_valid(state_json) THEN
                 json_extract(state_json,'$.status')='running' OR
                 (json_extract(state_json,'$.status')='waiting_review'
                  AND json_extract(state_json,'$.governed_submission_started')=1
                  AND COALESCE(json_extract(state_json,'$.recovery_hold'),0)=0
                  AND json_extract(state_json,'$.governed_task_id') IS NULL
                  AND json_extract(state_json,'$.governed_mission_id') IS NULL
                  AND json_extract(state_json,'$.agent_session_id') IS NULL)
                 ELSE 0 END ORDER BY rowid LIMIT 100""").fetchall()
            if not rows:return counts
            for row in rows:
                state=json.loads(row["state_json"])
                if (state.get("id")!=row["id"] or state.get("project_scope")!=row["project_scope"]
                        or state.get("session_scope")!=row["session_scope"]):
                    # Fail closed on contradictory stored scope, without exposing content.
                    raise ValueError("Interrupted request identity or scope mismatch")
                result,field,child=find_child(conn,state)
                if result=="linked":
                    state[field]=child
                state.update(status="waiting_review",recovery_hold=True,
                             recovery_result=result,updated_at=time.time(),
                             answer=("Recovered existing work linkage. Review the retained job before explicitly continuing."
                                     if result=="linked" else
                                     "Interrupted request held for review. No uniquely matching retained child was confirmed. No automatic replay."))
                conn.execute("UPDATE conversation_requests SET state_json=? WHERE id=?",(json.dumps(state),row["id"]))
                counts[result]=counts.get(result,0)+1
            conn.commit()
