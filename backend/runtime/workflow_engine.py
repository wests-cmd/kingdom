import time
import secrets
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel, Field


class AutonomyLevel(int, Enum):
    LEVEL_0_SUGGEST = 0
    LEVEL_1_REVERSIBLE_LOW_RISK = 1
    LEVEL_2_APPROVED_WORKFLOWS = 2
    LEVEL_3_ADAPTIVE_BOUNDED = 3
    LEVEL_4_HIGH_RISK = 4


class WorkflowResourceBudget(BaseModel):
    max_steps: int = 20
    max_execution_time_sec: float = 300.0
    max_cost_usd: float = 5.0
    max_tool_calls: int = 15
    max_network_calls: int = 10

    # Consumption counters
    used_steps: int = 0
    used_execution_time_sec: float = 0.0
    used_cost_usd: float = 0.0
    used_tool_calls: int = 0
    used_network_calls: int = 0

    def consume_step(self, cost_usd: float = 0.0, is_tool_call: bool = False, is_network_call: bool = False) -> None:
        self.used_steps += 1
        self.used_cost_usd += cost_usd
        if is_tool_call:
            self.used_tool_calls += 1
        if is_network_call:
            self.used_network_calls += 1

        if self.used_steps > self.max_steps:
            raise RuntimeError(f"Workflow budget exceeded: Max steps ({self.max_steps}) breached.")
        if self.used_cost_usd > self.max_cost_usd:
            raise RuntimeError(f"Workflow budget exceeded: Max cost (${self.max_cost_usd}) breached.")
        if self.used_tool_calls > self.max_tool_calls:
            raise RuntimeError(f"Workflow budget exceeded: Max tool calls ({self.max_tool_calls}) breached.")
        if self.used_network_calls > self.max_network_calls:
            raise RuntimeError(f"Workflow budget exceeded: Max network calls ({self.max_network_calls}) breached.")


class WorkflowState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_FOR_AUTHORIZATION = "WAITING_FOR_AUTHORIZATION"
    REQUIRES_HUMAN_APPROVAL = "REQUIRES_HUMAN_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    BLOCKED_BY_INCIDENT_MODE = "BLOCKED_BY_INCIDENT_MODE"


class WorkflowContract(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf_{secrets.token_hex(6)}")
    actor_identity_id: str
    objective: str
    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_1_REVERSIBLE_LOW_RISK
    required_capabilities: List[str] = Field(default_factory=list)
    risk_ceiling: str = "MEDIUM"
    budget: WorkflowResourceBudget = Field(default_factory=WorkflowResourceBudget)
    state: WorkflowState = WorkflowState.PENDING
    created_at: float = Field(default_factory=time.time)
    completed_steps: List[Dict[str, Any]] = Field(default_factory=list)
    compensating_actions: List[Dict[str, Any]] = Field(default_factory=list)


class CheckpointManager:

    def __init__(self):
        self.checkpoints: Dict[str, WorkflowContract] = {}

    def save_checkpoint(self, workflow: WorkflowContract) -> None:
        # Save deep copy of workflow state
        self.checkpoints[workflow.workflow_id] = workflow.model_copy(deep=True)

    def load_checkpoint(self, workflow_id: str) -> Optional[WorkflowContract]:
        checkpoint = self.checkpoints.get(workflow_id)
        if checkpoint:
            return checkpoint.model_copy(deep=True)
        return None


class CompensationEngine:

    def __init__(self):
        self.handlers: Dict[str, Callable[[Dict[str, Any]], bool]] = {}

    def register_compensator(self, action_type: str, handler: Callable[[Dict[str, Any]], bool]) -> None:
        self.handlers[action_type] = handler

    def execute_compensation(self, action: Dict[str, Any]) -> bool:
        action_type = action.get("action_type")
        handler = self.handlers.get(action_type)
        if not handler:
            return False
        try:
            return handler(action.get("params", {}))
        except Exception:
            return False


class EmergencyIncidentMode:

    def __init__(self):
        self.active: bool = False
        self.activated_at: Optional[float] = None
        self.activated_by: Optional[str] = None
        self.reason: Optional[str] = None

    def activate_emergency_lockdown(self, operator: str, reason: str) -> None:
        self.active = True
        self.activated_at = time.time()
        self.activated_by = operator
        self.reason = reason

    def deactivate_emergency_lockdown(self, operator: str) -> None:
        self.active = False
        self.activated_at = None
        self.activated_by = operator
        self.reason = "Deactivated by operator"

    def enforce_incident_check(self) -> None:
        if self.active:
            raise PermissionError(
                f"Emergency Incident Lockdown ACTIVE (Activated by {self.activated_by}: {self.reason}). All autonomous operations frozen."
            )
