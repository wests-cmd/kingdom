from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.runtime.engine import RuntimeEngine
from backend.security.capabilities import ALL_CAPABILITIES, DEFAULT_KNIGHT_CAPABILITIES, PRIVILEGED_CAPABILITIES
from backend.security.risk import CAPABILITY_RISK_MAP
from backend.security.zero_trust import ZeroTrust
from backend.skills.models import Skill, SkillTrustLevel, SkillLifecycleState, SkillDependency, SkillRequirement
from backend.skills.lifecycle import SkillLifecycleManager, SkillLifecycleError
from backend.skills.bundles import SkillBundle, SkillBundleManager
from backend.learning.collector import LearningCollector
from backend.learning.evaluator import LearningEvaluator
from backend.learning.experiment import LearningExperimentRunner

from backend.cluster.identity import KingdomIdentity, KnightIdentity
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.pairing import pairing_manager
from backend.cluster.capabilities import capability_authorizer
from backend.cluster.heartbeat import heartbeat_manager
from backend.cluster.audit import audit_logger

router = APIRouter()
engine = RuntimeEngine()
zero_trust = engine.security

# Skills & Learning Managers Setup
sample_skill = Skill(
    id="skill-web-research",
    name="Web Research",
    version="1.0.0",
    description="Automated web research and document analysis",
    department="Research",
    trust_level=SkillTrustLevel.VERIFIED,
    state=SkillLifecycleState.ACTIVE,
    permissions=["network.outbound"],
    dependencies=SkillDependency(
        required_tools=["http_client"],
        required_capabilities=["model.inference"],
        required_models=["gpt-4o"]
    )
)

lifecycle_manager = SkillLifecycleManager(
    available_tools=["http_client", "pdf_parser"],
    available_capabilities=["model.inference", "python.exec"],
    available_models=["gpt-4o"],
    granted_permissions=["network.outbound", "filesystem.read"]
)
lifecycle_manager.save(sample_skill)
lifecycle_manager.install(sample_skill.id)
lifecycle_manager.activate(sample_skill.id, governance_approved=True)

bundle_manager = SkillBundleManager(available_skills=[sample_skill])
learning_collector = LearningCollector()
learning_evaluator = LearningEvaluator(learning_collector)
learning_runner = LearningExperimentRunner(learning_collector, lifecycle_manager=lifecycle_manager)

# Attach skills_manager to runtime engine for MCP server discovery
engine.skills_manager = lifecycle_manager

# Request Models
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

class PromoteProposalRequest(BaseModel):
    experiment_id: str

class RollbackSkillRequest(BaseModel):
    from_version: str
    to_version: str
    reason: str = "Administrator requested rollback"

class NodePairRequest(BaseModel):
    code: str
    knight_public_identity: dict[str, Any]
    requested_capabilities: list[str] = Field(default_factory=list)
    signature: str | None = None
    is_local: bool = False

class NodeApproveRequest(BaseModel):
    granted_capabilities: list[str] = Field(default_factory=list)

class NodeRejectRequest(BaseModel):
    reason: str = "Rejected by administrator"

class NodeCapabilitiesRequest(BaseModel):
    granted_capabilities: list[str]

# --- RUNTIME ENDPOINTS ---

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

# --- SKILLS API ENDPOINTS ---

@router.get("/skills")
def list_skills():
    return [s.model_dump() for s in lifecycle_manager.skills.values()]

@router.get("/skills/map")
def get_skill_map():
    return lifecycle_manager.skill_map.get_map_structure()

@router.get("/skills/{skill_id}/readiness")
def check_skill_readiness(skill_id: str):
    skill = lifecycle_manager.skills.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found.")
    return lifecycle_manager.skill_map.check_readiness(
        skill=skill,
        available_tools=lifecycle_manager.available_tools,
        available_capabilities=lifecycle_manager.available_capabilities,
        available_models=lifecycle_manager.available_models,
        granted_permissions=lifecycle_manager.granted_permissions
    )

@router.post("/skills", status_code=status.HTTP_201_CREATED)
def save_skill(skill: Skill):
    return lifecycle_manager.save(skill).model_dump()

@router.post("/skills/{skill_id}/install")
def install_skill(skill_id: str):
    try:
        return lifecycle_manager.install(skill_id).model_dump()
    except SkillLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/skills/{skill_id}/activate")
def activate_skill(skill_id: str, governance_approved: bool = True):
    try:
        return lifecycle_manager.activate(skill_id, governance_approved=governance_approved).model_dump()
    except SkillLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/skills/{skill_id}/deactivate")
def deactivate_skill(skill_id: str):
    try:
        return lifecycle_manager.deactivate(skill_id).model_dump()
    except SkillLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.delete("/skills/{skill_id}")
def remove_skill(skill_id: str):
    try:
        return lifecycle_manager.remove(skill_id).model_dump()
    except SkillLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

# --- LEARNING API ENDPOINTS ---

@router.get("/learning/activity")
def get_learning_activity():
    return {
        "proposals": [p.model_dump() for p in learning_evaluator.proposals],
        "experiments": [e.model_dump() for e in learning_runner.experiments.values()],
        "promotions": [p.model_dump() for p in learning_runner.promotions],
        "rollbacks": [r.model_dump() for r in learning_runner.rollbacks]
    }

@router.post("/learning/proposals/{proposal_id}/promote")
def promote_learning_proposal(proposal_id: str, request: PromoteProposalRequest):
    proposal = next((p for p in learning_evaluator.proposals if p.id == proposal_id), None)
    if not proposal:
        raise HTTPException(status_code=404, detail="Improvement proposal not found")
    try:
        rec = learning_runner.promote_candidate(
            experiment_id=request.experiment_id,
            proposal=proposal,
            promoter="admin",
            governance_level=3
        )
        return rec.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/learning/skills/{skill_id}/rollback")
def rollback_skill(skill_id: str, request: RollbackSkillRequest):
    rec = learning_runner.trigger_rollback(
        skill_id=skill_id,
        from_version=request.from_version,
        to_version=request.to_version,
        reason=request.reason
    )
    return rec.model_dump()

# --- SECURITY API ENDPOINTS ---

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

# --- CLUSTER / MULTI-NODE ENDPOINTS ---

@router.get("/nodes/identity")
def get_kingdom_identity():
    k_identity = KingdomIdentity.get_or_create()
    return k_identity.get_public_identity()

@router.get("/nodes")
def list_cluster_nodes(node_state: str | None = Query(default=None)):
    state_filter = NodeState(node_state) if node_state else None
    return node_registry.list_nodes(state=state_filter)

@router.get("/nodes/pending")
def list_pending_nodes():
    return node_registry.list_nodes(state=NodeState.PENDING_APPROVAL)

@router.get("/nodes/{node_id}")
def get_cluster_node(node_id: str):
    node = node_registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found in cluster registry")
    return node

@router.post("/nodes/invitation", status_code=status.HTTP_201_CREATED)
def create_pairing_invitation(ttl_seconds: int = Query(default=600, ge=60, le=3600)):
    return pairing_manager.create_invitation(ttl_seconds=ttl_seconds)

@router.post("/nodes/pair")
def process_node_pairing(request: NodePairRequest):
    k_identity = KingdomIdentity.get_or_create()
    req_payload = {
        "code": request.code,
        "expected_kingdom_id": k_identity.node_id,
        "knight_public_identity": request.knight_public_identity,
        "requested_capabilities": request.requested_capabilities,
        "signature": request.signature,
        "is_local": request.is_local
    }
    res = pairing_manager.process_pairing_request(req_payload)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    audit_logger.log_event("pairing_requested", res["node_id"], k_identity.node_id, req_payload)
    return res

@router.post("/nodes/{node_id}/approve")
def approve_cluster_node(node_id: str, request: NodeApproveRequest):
    k_identity = KingdomIdentity.get_or_create()
    node = capability_authorizer.approve_node_and_capabilities(node_id, request.granted_capabilities)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    audit_logger.log_event("node_approved", node_id, k_identity.node_id, {"granted": request.granted_capabilities})
    return node

@router.post("/nodes/{node_id}/reject")
def reject_cluster_node(node_id: str, request: NodeRejectRequest):
    k_identity = KingdomIdentity.get_or_create()
    node = node_registry.update_node_state(node_id, NodeState.REJECTED, reason=request.reason)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    audit_logger.log_event("node_rejected", node_id, k_identity.node_id, {"reason": request.reason})
    return node

@router.post("/nodes/{node_id}/revoke")
def revoke_cluster_node(node_id: str, reason: str = Query(default="Administrator revoked node")):
    k_identity = KingdomIdentity.get_or_create()
    node = capability_authorizer.revoke_node(node_id, reason=reason)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    audit_logger.log_event("node_revoked", node_id, k_identity.node_id, {"reason": reason})
    return node

@router.post("/nodes/{node_id}/reconnect")
def reconnect_cluster_node(node_id: str):
    node = node_registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    res = heartbeat_manager.ping(node_id)
    return res

@router.get("/nodes/{node_id}/health")
def check_node_health(node_id: str):
    node = node_registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {
        "id": node_id,
        "health": node.get("health", "unknown"),
        "node_state": node.get("node_state"),
        "last_heartbeat": node.get("last_heartbeat")
    }

@router.get("/nodes/{node_id}/capabilities")
def get_node_capabilities(node_id: str):
    node = node_registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {
        "requested_capabilities": node.get("capabilities", []),
        "granted_capabilities": node.get("granted_capabilities", [])
    }

@router.post("/nodes/{node_id}/capabilities")
def update_node_capabilities(node_id: str, request: NodeCapabilitiesRequest):
    node = capability_authorizer.update_capabilities(node_id, request.granted_capabilities)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node
