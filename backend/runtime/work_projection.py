"""Read-only bounded work projection over existing durable repositories.

No new state, authority, scheduler, inference, retry or completion transition.
Source statuses are deliberately preserved rather than synthesized into success.
"""
import json
import math
import re
from collections import Counter, defaultdict

SOURCES = {"request":"conversation_requests", "mission":"missions", "agent":"agent_sessions", "task":"tasks"}
STATUS = {
    "queued":"queued", "ready":"queued", "approved":"queued",
    "running":"active", "thinking":"active", "leased":"active",
    "waiting_tools":"waiting", "waiting_approval":"attention", "waiting_review":"attention",
    "needs_review":"attention", "draft":"attention", "recovery_required":"attention",
    "blocked":"attention", "denied":"attention", "budget_exhausted":"attention", "failed":"attention",
    "completed":"recorded_finished", "succeeded":"recorded_finished", "cancelled":"cancelled",
}
MAX_RECORDS = 100
ROUTES = {"quick","agent","harness","delegate","commander","time","status","priorities","work","help","harnesses"}


def mapping(value):
    return value if isinstance(value,dict) else {}


def safe_id(value):
    return value if isinstance(value,str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}",value) else None


def safe_time(value):
    return value if type(value) in (int,float) and math.isfinite(value) and value>=0 else None


def state_of(value):
    state=value.lower() if isinstance(value,str) else "unknown"
    return state if state in STATUS else "unknown"


def receipt_kind(row):
    """Describe retained receipt shape only; do not independently recertify effects."""
    if row["status"] not in {"completed","succeeded"}:
        return "not_claimed"
    if row["kind"]!="task":
        return "recorded_only"
    result=mapping(row["_data"].get("result"))
    items=result.get("results")
    if isinstance(items,list) and items and all(
            mapping(mapping(item).get("verification")).get("state")=="VERIFIED"
            and "output" in mapping(mapping(item).get("outcome")) for item in items):
        return "retained_controller_receipt"
    worker=result.get("executed_by")
    if (mapping(result.get("verification")).get("state")=="VERIFIED" and safe_id(worker)
            and "output" in result and (not row["_data"].get("assigned_knight") or row["_data"]["assigned_knight"]==worker)):
        return "retained_controller_receipt"
    return "recorded_only"


def load_rows(conn,kind,limit):
    table=SOURCES[kind]  # fixed internal allowlist, never user input
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
        if kind=="task":
            raise ValueError("Task repository unavailable")
        return [],False,0
    if kind=="task":
        query="SELECT id,status,metadata_json,result_json,assigned_knight,created_at,updated_at FROM tasks ORDER BY updated_at DESC,id LIMIT ?"
    elif kind=="request":
        query="SELECT id,project_scope,session_scope,state_json FROM conversation_requests ORDER BY rowid DESC LIMIT ?"
    else:
        query=f"SELECT id,state_json FROM {table} ORDER BY rowid DESC LIMIT ?"
    saved=conn.execute(query,(limit+1,)).fetchall()
    rows=[]
    invalid=0
    for item in saved[:limit]:
        try:
            if kind=="task":
                data=dict(item)
                data["metadata"]=json.loads(data.pop("metadata_json") or "{}")
                data["result"]=json.loads(data.pop("result_json") or "null")
            else:
                data=json.loads(item["state_json"])
                if not isinstance(data,dict) or data.get("id")!=item["id"]:
                    raise ValueError("Identity mismatch")
                if kind=="request" and any(not isinstance(data.get(k),str) or data.get(k)!=item[k] for k in ("project_scope","session_scope")):
                    raise ValueError("Request scope mismatch")
            ident=safe_id(item["id"])
            if not ident:raise ValueError("Invalid retained identity")
            state=state_of(data.get("status"))
            row={"id":ident,"kind":kind,"status":state,"category":STATUS.get(state,"unknown"),
                 "updated_at":safe_time(data.get("updated_at")) or safe_time(data.get("created_at")),
                 "_data":data}
            row["evidence"]=receipt_kind(row)
            if kind=="request":
                route=data.get("route")
                row["route"]=route if isinstance(route,str) and route in ROUTES else "unknown"
            rows.append(row)
        except (ValueError,TypeError,KeyError,OverflowError):
            invalid+=1
    return rows,len(saved)>limit,invalid


def project_work(database, *, project_scope=None, session_scope=None, limit=MAX_RECORDS):
    if (project_scope is None)!=(session_scope is None):
        raise ValueError("Both project and conversation scopes are required together")
    if type(limit) is not int or not 1<=limit<=MAX_RECORDS:
        raise ValueError("Invalid projection limit")
    if project_scope is not None and (not isinstance(project_scope,str) or not isinstance(session_scope,str)
            or not 1<=len(project_scope)<=200 or not 1<=len(session_scope)<=100):
        raise ValueError("Invalid exact scope")
    with database.get_connection() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        rows={}
        truncated=[]
        invalid=0
        for kind in SOURCES:
            records,partial,errors=load_rows(conn,kind,limit)
            rows.update({(kind,r["id"]):r for r in records})
            if partial:truncated.append(kind)
            invalid+=errors

    # Gather only retained forward links. A task must also identify its parent
    # in metadata. Historical tasks lacking a parent-side retained link remain
    # standalone; arbitrary metadata alone cannot hide work.
    from backend.runtime.request_origin import request_origin
    candidates=defaultdict(set)
    issues=Counter()
    def link(parent,kind,ident,valid):
        child=(kind,ident) if safe_id(ident) else None
        if child is None or child not in rows:
            issues[parent]+=1
        elif not valid(rows[child]["_data"]):
            issues[parent]+=1
        else:
            candidates[child].add(parent)

    for key,row in rows.items():
        data=row["_data"]
        if row["kind"]=="request":
            if data.get("governed_task_id"):
                link(key,"task",data["governed_task_id"],lambda child:
                     mapping(child.get("metadata")).get("conversation_request_id")==row["id"]
                     and mapping(child.get("metadata")).get("project_scope")==data.get("project_scope"))
            if data.get("governed_mission_id"):
                link(key,"mission",data["governed_mission_id"],lambda child:
                     child.get("request_origin")==request_origin(data) or (project_scope is None and "request_origin" not in child))
            if data.get("agent_session_id"):
                link(key,"agent",data["agent_session_id"],lambda child:child.get("workspace")==data.get("project_scope")
                     and (child.get("request_origin")==request_origin(data) or (project_scope is None and "request_origin" not in child)))
        elif row["kind"]=="mission":
            for step,record in mapping(data.get("steps")).items():
                ident=mapping(record).get("task_id")
                if ident:
                    link(key,"task",ident,lambda child:
                         mapping(child.get("metadata")).get("mission_id")==row["id"]
                         and mapping(child.get("metadata")).get("step_id")==step
                         and mapping(child.get("metadata")).get("mission_version")==data.get("version"))
        elif row["kind"]=="agent":
            pending=data.get("pending",[])
            if isinstance(pending,list):
                for record in pending:
                    ident=mapping(record).get("task_id")
                    if ident:
                        link(key,"task",ident,lambda child:
                             mapping(child.get("metadata")).get("agent_session_id")==row["id"]
                             and mapping(child.get("metadata")).get("_mission_step_key")==mapping(record).get("key")
                             and bool(mapping(record).get("key")))

    parent_of={}
    children=defaultdict(list)
    for child,parents in candidates.items():
        if len(parents)!=1:
            for parent in parents:issues[parent]+=1
            continue
        parent=next(iter(parents))
        # When parent sources are truncated, an unobserved request could also
        # reference the same mission/agent. No scoped cross-reference is exposed.
        if project_scope is not None and (truncated or invalid):
            issues[parent]+=1
            continue
        parent_of[child]=parent
        children[parent].append(child)

    def view(key):
        row=rows[key]
        return {**{k:v for k,v in row.items() if k!="_data"},
                "unresolved_links":issues[key],"children":[view(c) for c in sorted(children[key])]}

    roots=[key for key in rows if key not in parent_of]
    if project_scope is not None:
        roots=[key for key in roots if key[0]=="request"
               and rows[key]["_data"].get("project_scope")==project_scope
               and rows[key]["_data"].get("session_scope")==session_scope]
    items=[view(key) for key in sorted(roots,key=lambda k:(-(rows[k]["updated_at"] or 0),k))]
    counts=dict(Counter(item["category"] for item in items))
    return {"schema":"kingdom.work-projection.v1","scope":"conversation" if project_scope is not None else "owner",
            "project_scope":project_scope,"session_scope":session_scope,"items":items,"root_counts":counts,
            "complete_snapshot":not truncated and not invalid,
            "truncated_sources":truncated,"invalid_records":invalid,
            "scope_note":"Recent bounded records, linked only by retained references. Missing or ambiguous links are not success. Recorded completion is not independent effect certification."}
