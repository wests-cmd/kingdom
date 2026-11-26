"""Internal request lineage for observational linkage, never authorization."""
import json


def request_origin(state):
    return {"request_id":state["id"],"project_scope":state["project_scope"],"session_scope":state["session_scope"]}


def validate_origin(database,origin,route,*,workspace=None):
    if (not isinstance(origin,dict) or set(origin)!={"request_id","project_scope","session_scope"}
            or any(not isinstance(origin[k],str) or not 1<=len(origin[k])<=n
                   for k,n in (("request_id",128),("project_scope",200),("session_scope",100)))):
        raise ValueError("Invalid internal request lineage")
    with database.get_connection() as conn:
        row=conn.execute("SELECT session_scope,project_scope,state_json FROM conversation_requests WHERE id=?",
                         (origin["request_id"],)).fetchone()
    if not row:raise ValueError("Originating request is unavailable")
    try:
        state=json.loads(row["state_json"])
        valid=(row["session_scope"]==origin["session_scope"] and row["project_scope"]==origin["project_scope"]
               and request_origin(state)==origin and state.get("route")==route and state.get("status")=="running"
               and (workspace is None or workspace==origin["project_scope"]))
    except (ValueError,KeyError,TypeError,AttributeError):
        valid=False
    if not valid:raise ValueError("Originating request changed")
    return dict(origin)
