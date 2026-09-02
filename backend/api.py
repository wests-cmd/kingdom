from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Body
from backend.runtime.engine import runtime_engine
from backend.cluster.node_registry import node_registry
from backend.events.event_bus import event_bus
from backend.memory.persistence import memory_store
from backend.security.permissions import permission_manager, CAPABILITIES
from backend.security.zero_trust import ZeroTrust
from backend.security.approval_engine import approval_engine
from backend.security.audit_log import audit_logger
from backend.skills.skill_engine import skill_engine, DEPARTMENTS

router = APIRouter()
zero_trust = ZeroTrust()

# --- RUNTIME ENDPOINTS ---

@router.get("/status")
def status():
    return runtime_engine.status()

@router.post("/start")
def start():
    return runtime_engine.start()

@router.post("/stop")
def stop():
    return runtime_engine.stop()

@router.get("/mode")
def mode():
    return runtime_engine.get_mode()

# --- TASK ENDPOINTS ---

@router.post("/tasks")
def create_task(payload: Dict[str, Any] = Body(...)):
    task_type = payload.get("type", "generic")
    input_data = payload.get("input", {})
    actor = payload.get("actor")

    if not isinstance(input_data, (dict, list, str, int, float, bool)):
        raise HTTPException(status_code=400, detail="Invalid input payload")

    task = runtime_engine.create_task(task_type, input_data, actor=actor)
    return task

@router.get("/tasks")
def list_tasks(status: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=1000)):
    return runtime_engine.list_tasks(status=status, limit=limit)

@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = runtime_engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    task = runtime_engine.cancel_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# --- KNIGHT ENDPOINTS ---

@router.get("/knights")
def list_knights():
    return node_registry.list_knights()

@router.get("/knights/{knight_id}")
def get_knight(knight_id: str):
    knight = node_registry.get_knight(knight_id)
    if not knight:
        raise HTTPException(status_code=404, detail="Knight not found")
    return knight

# --- EVENT HISTORY ENDPOINTS ---

@router.get("/events")
def get_events(
    task_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    return event_bus.get_events(task_id=task_id, event_type=event_type, limit=limit)

# --- MEMORY ENDPOINTS ---

@router.post("/memory")
def add_memory(payload: Dict[str, Any] = Body(...)):
    content = payload.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="'content' field is required")

    metadata = payload.get("metadata", {})
    source = payload.get("source", "user")
    trust = payload.get("trust", 1.0)

    return memory_store.add_memory(content=content, metadata=metadata, source=source, trust=trust)

@router.get("/memory/search")
def search_memory(query: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500)):
    return memory_store.search_memory(query=query, limit=limit)

# --- SKILL MAP & BUNDLE ENDPOINTS ---

@router.get("/skills")
def list_skills():
    return skill_engine.list_skills()

@router.get("/skills/departments")
def list_departments():
    return DEPARTMENTS

@router.get("/skills/bundles")
def list_bundles():
    return skill_engine.list_bundles()

@router.post("/skills/bundles")
def create_bundle(payload: Dict[str, Any] = Body(...)):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="'name' is required")
    description = payload.get("description", "")
    skill_ids = payload.get("skill_ids", [])
    return skill_engine.create_bundle(name=name, description=description, skill_ids=skill_ids)

@router.delete("/skills/bundles/{bundle_id}")
def delete_bundle(bundle_id: str):
    skill_engine.repo.delete_bundle(bundle_id)
    return {"status": "deleted", "bundle_id": bundle_id}

@router.get("/skills/{skill_id}")
def get_skill(skill_id: str):
    sk = skill_engine.get_skill(skill_id)
    if not sk:
        raise HTTPException(status_code=404, detail="Skill not found")
    return sk

@router.post("/skills")
def save_skill(payload: Dict[str, Any] = Body(...)):
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="'name' is required")
    return skill_engine.save_skill(payload)

@router.get("/skills/{skill_id}/dependencies")
def resolve_skill_dependencies(skill_id: str, chosen_departments: Optional[str] = Query(None)):
    depts = [d.strip() for d in chosen_departments.split(",")] if chosen_departments else None
    return skill_engine.resolve_dependencies(skill_id, chosen_departments=depts)

@router.post("/skills/{skill_id}/install")
def install_skill(skill_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    chosen_depts = (payload or {}).get("chosen_departments")
    res = skill_engine.install_skill(skill_id, chosen_departments=chosen_depts)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/skills/{skill_id}/activate")
def activate_skill(skill_id: str):
    res = skill_engine.activate_skill(skill_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/skills/{skill_id}/deactivate")
def deactivate_skill(skill_id: str):
    res = skill_engine.deactivate_skill(skill_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: str):
    skill_engine.repo.delete_skill(skill_id)
    return {"status": "deleted", "skill_id": skill_id}

# --- SECURITY ENDPOINTS ---

@router.get("/security/status")
def security_status():
    pending = len(approval_engine.list_requests(status="pending"))
    events = len(audit_logger.get_events(limit=1000))
    return {
        "status": "active",
        "zero_trust": True,
        "deny_by_default": True,
        "capabilities_count": len(CAPABILITIES),
        "pending_approvals": pending,
        "audit_events_count": events
    }

@router.get("/security/policies")
def security_policies():
    return {
        "capabilities": CAPABILITIES,
        "roles": permission_manager.roles,
        "deny_by_default": True
    }

@router.get("/security/permissions")
def security_permissions():
    return {
        "capabilities": CAPABILITIES,
        "roles": permission_manager.roles
    }

@router.post("/security/authorize")
def security_authorize(payload: Dict[str, Any] = Body(...)):
    actor = payload.get("actor")
    capability = payload.get("capability")
    if not actor or not capability:
        raise HTTPException(status_code=400, detail="'actor' and 'capability' fields are required")

    result = zero_trust.validate(actor, required_capability=capability)
    audit_logger.log_event(
        actor=actor.get("id") if isinstance(actor, dict) else str(actor),
        node="api",
        operation="authorize_check",
        capability=capability,
        decision="authorized" if result.get("authorized") else "denied",
        reason=result.get("reason", "")
    )
    return result

@router.get("/security/approvals")
def get_approvals(status: Optional[str] = Query(None)):
    return approval_engine.list_requests(status=status)

@router.post("/security/approvals")
def create_approval(payload: Dict[str, Any] = Body(...)):
    node = payload.get("requesting_node", "api_client")
    component = payload.get("component", "user")
    capability = payload.get("requested_capability", "process.execute")
    action = payload.get("action", "custom_action")
    reason = payload.get("reason", "Requested via API")
    risk = payload.get("risk_level")
    params = payload.get("parameters", {})

    req = approval_engine.create_request(
        requesting_node=node,
        component=component,
        requested_capability=capability,
        action=action,
        reason=reason,
        risk_level=risk,
        parameters=params
    )

    audit_logger.log_event(
        actor=node,
        node=node,
        operation=action,
        capability=capability,
        decision="approval_requested",
        reason=reason,
        approval_id=req["approval_id"]
    )

    return req

@router.post("/security/approvals/{approval_id}/approve")
def approve_request(approval_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    approving_identity = (payload or {}).get("approving_identity", "admin")
    res = approval_engine.approve(approval_id, approving_identity=approving_identity)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])

    audit_logger.log_event(
        actor=approving_identity,
        node="api",
        operation="approve",
        capability=res.get("requested_capability", "approval"),
        decision="approved",
        reason="Human admin approved request",
        approval_id=approval_id
    )
    return res

@router.post("/security/approvals/{approval_id}/deny")
def deny_request(approval_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    denying_identity = (payload or {}).get("denying_identity", "admin")
    reason = (payload or {}).get("reason", "Denied by administrator")
    res = approval_engine.deny(approval_id, denying_identity=denying_identity, reason=reason)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])

    audit_logger.log_event(
        actor=denying_identity,
        node="api",
        operation="deny",
        capability=res.get("requested_capability", "approval"),
        decision="denied",
        reason=reason,
        approval_id=approval_id
    )
    return res

@router.get("/security/audit")
def get_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    decision: Optional[str] = Query(None),
    actor: Optional[str] = Query(None)
):
    return audit_logger.get_events(limit=limit, decision=decision, actor=actor)
