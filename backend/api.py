from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.runtime.engine import RuntimeEngine
from backend.security.capabilities import ALL_CAPABILITIES, DEFAULT_KNIGHT_CAPABILITIES, PRIVILEGED_CAPABILITIES
from backend.security.risk import CAPABILITY_RISK_MAP

router = APIRouter()
engine = RuntimeEngine()


class TaskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModeRequest(BaseModel):
    mode: str


class ModelRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    model: str | None = None
    provider: str | None = None


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0)


class MapRequest(BaseModel):
    graph: dict[str, Any]


class SecurityAuthorizeRequest(BaseModel):
    actor_id: str = "system"
    capability: str
    operation: str
    prompt: str | None = None
    token: str | None = None
    approval_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class SecurityApprovalCreateRequest(BaseModel):
    capability: str
    operation: str
    reason: str = ""
    requesting_actor: str = "system"
    risk_level: str = "HIGH"
    parameters: dict[str, Any] = Field(default_factory=dict)


class SecurityApprovalDecisionRequest(BaseModel):
    reason: str = "Administrator decision"
    approver: str = "admin"


@router.get("/status")
def runtime_status():
    return engine.status()


@router.post("/start")
async def start():
    return await engine.start()


@router.post("/stop")
async def stop():
    return await engine.stop()


@router.get("/mode")
def mode():
    return {"mode": engine.get_mode()}


@router.put("/mode")
def set_mode(request: ModeRequest):
    try:
        return engine.set_mode(request.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(request: TaskRequest):
    try:
        return engine.submit_task(request.prompt, request.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tasks")
def list_tasks(task_status: str | None = Query(default=None, alias="status")):
    return engine.tasks.list(task_status)


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = engine.tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    try:
        return engine.cancel_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/events")
def event_history(limit: int = Query(default=50, ge=1, le=200)):
    return engine.events.history(limit)


@router.get("/knights")
def knights():
    return engine.swarm.status()


@router.get("/models")
async def model_health():
    return await engine.models.health()


@router.post("/models/generate")
async def generate(request: ModelRequest):
    try:
        return await engine.models.generate(request.prompt, request.model, request.provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/models/stream")
async def stream(request: ModelRequest):
    provider = request.provider or engine.models.default_provider
    if provider != "ollama":
        raise HTTPException(status_code=503, detail="Streaming currently requires the Ollama provider")

    async def events():
        async for token in engine.models.stream(request.prompt, request.model, provider):
            yield f"data: {token}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/memory")
def memory_entries(limit: int = Query(default=100, ge=1, le=500)):
    return engine.memory.entries(limit)


@router.post("/memory", status_code=status.HTTP_201_CREATED)
def add_memory(request: MemoryRequest):
    entry = engine.memory.add(request.content, request.metadata, request.weight)
    engine.events.publish("memory.recorded", {"entry_id": entry["id"]})
    return entry


@router.get("/memory/search")
def search_memory(query: str = Query(min_length=1), limit: int = Query(default=5, ge=1, le=50)):
    return engine.memory.search(query, limit)


@router.get("/memory/graph")
def memory_graph():
    return engine.memory.graph()


@router.post("/memory/snapshot", status_code=status.HTTP_201_CREATED)
def memory_snapshot():
    return {"path": engine.memory.snapshot()}


@router.get("/maps")
def list_maps():
    return engine.maps.list()


@router.post("/maps/{name}", status_code=status.HTTP_201_CREATED)
def export_map(name: str, request: MapRequest):
    try:
        return {"path": engine.maps.export(name, request.graph)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/maps/{name}")
def import_map(name: str):
    try:
        return engine.maps.load(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# --- Security API Endpoints ---


@router.get("/security/status")
def security_status():
    pending_approvals = engine.security.approvals.list_requests(status="pending")
    return {
        "enabled": True,
        "mode": "zero_trust",
        "registered_nodes": len(engine.security.nodes.list_nodes()),
        "pending_approvals_count": len(pending_approvals),
        "audit_logs_count": len(engine.security.audit.history(limit=1000)),
    }


@router.get("/security/policies")
def security_policies():
    return {
        "all_capabilities": sorted(list(ALL_CAPABILITIES)),
        "default_knight_capabilities": sorted(list(DEFAULT_KNIGHT_CAPABILITIES)),
        "privileged_capabilities": sorted(list(PRIVILEGED_CAPABILITIES)),
        "risk_mapping": {cap: risk.value for cap, risk in CAPABILITY_RISK_MAP.items()},
    }


@router.get("/security/permissions")
def security_permissions():
    nodes = engine.security.nodes.list_nodes()
    return {"nodes": nodes}


@router.post("/security/authorize")
def security_authorize(request: SecurityAuthorizeRequest):
    return engine.security.authorize(
        actor_id=request.actor_id,
        capability=request.capability,
        operation=request.operation,
        prompt=request.prompt,
        token=request.token,
        parameters=request.parameters,
        approval_id=request.approval_id,
    )


@router.get("/security/approvals")
def security_list_approvals(approval_status: str | None = Query(default=None, alias="status")):
    return engine.security.approvals.list_requests(status=approval_status)


@router.post("/security/approvals", status_code=status.HTTP_201_CREATED)
def security_create_approval(request: SecurityApprovalCreateRequest):
    return engine.security.approvals.create_request(
        capability=request.capability,
        operation=request.operation,
        reason=request.reason,
        requesting_actor=request.requesting_actor,
        risk_level=request.risk_level,
        parameters=request.parameters,
    )


@router.post("/security/approvals/{approval_id}/approve")
def security_approve(approval_id: str, request: SecurityApprovalDecisionRequest | None = None):
    approver = request.approver if request else "admin"
    try:
        req = engine.security.approvals.approve(approval_id, approver=approver)
        engine.security.audit.record(
            actor=approver,
            operation="approve",
            capability=req["capability"],
            decision="ALLOWED",
            reason="Human approval granted",
            approval_id=approval_id,
        )
        return req
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/security/approvals/{approval_id}/deny")
def security_deny(approval_id: str, request: SecurityApprovalDecisionRequest | None = None):
    denier = request.approver if request else "admin"
    reason = request.reason if request else "Denied by administrator"
    try:
        req = engine.security.approvals.deny(approval_id, reason=reason, denier=denier)
        engine.security.audit.record(
            actor=denier,
            operation="deny",
            capability=req["capability"],
            decision="DENIED",
            reason=f"Human approval denied: {reason}",
            approval_id=approval_id,
        )
        return req
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/security/audit")
def security_audit(
    limit: int = Query(default=100, ge=1, le=1000),
    actor: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    capability: str | None = Query(default=None),
):
    return engine.security.audit.history(limit=limit, actor=actor, decision=decision, capability=capability)
