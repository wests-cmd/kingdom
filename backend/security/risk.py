"""Operation risk classification for Kingdom."""

from __future__ import annotations

from enum import Enum
from typing import Any

from backend.security.capabilities import (
    CAPABILITY_AI_MAP_READ,
    CAPABILITY_AI_MAP_WRITE,
    CAPABILITY_DOCKER_EXECUTE,
    CAPABILITY_FILESYSTEM_DELETE,
    CAPABILITY_FILESYSTEM_READ,
    CAPABILITY_FILESYSTEM_WRITE,
    CAPABILITY_MEMORY_READ,
    CAPABILITY_MEMORY_WRITE,
    CAPABILITY_MODEL_INFERENCE,
    CAPABILITY_NETWORK_ACCESS,
    CAPABILITY_NODE_EXECUTE,
    CAPABILITY_NODE_REGISTER,
    CAPABILITY_PROCESS_EXECUTE,
    CAPABILITY_SYSTEM_ADMIN,
)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


CAPABILITY_RISK_MAP: dict[str, RiskLevel] = {
    CAPABILITY_FILESYSTEM_READ: RiskLevel.LOW,
    CAPABILITY_MEMORY_READ: RiskLevel.LOW,
    CAPABILITY_AI_MAP_READ: RiskLevel.LOW,
    CAPABILITY_MODEL_INFERENCE: RiskLevel.MEDIUM,
    CAPABILITY_MEMORY_WRITE: RiskLevel.MEDIUM,
    CAPABILITY_AI_MAP_WRITE: RiskLevel.MEDIUM,
    CAPABILITY_FILESYSTEM_WRITE: RiskLevel.MEDIUM,
    CAPABILITY_NODE_EXECUTE: RiskLevel.MEDIUM,
    CAPABILITY_FILESYSTEM_DELETE: RiskLevel.HIGH,
    CAPABILITY_PROCESS_EXECUTE: RiskLevel.HIGH,
    CAPABILITY_DOCKER_EXECUTE: RiskLevel.HIGH,
    CAPABILITY_NETWORK_ACCESS: RiskLevel.HIGH,
    CAPABILITY_NODE_REGISTER: RiskLevel.HIGH,
    CAPABILITY_SYSTEM_ADMIN: RiskLevel.HIGH,
}


class RiskClassifier:
    """Classifies risk levels of capabilities and operations."""

    @staticmethod
    def classify_capability(capability: str) -> RiskLevel:
        if capability in CAPABILITY_RISK_MAP:
            return CAPABILITY_RISK_MAP[capability]
        if capability.endswith(".execute") and capability not in (CAPABILITY_PROCESS_EXECUTE, CAPABILITY_DOCKER_EXECUTE):
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH

    @staticmethod
    def classify_operation(capability: str, operation_details: dict[str, Any] | None = None) -> RiskLevel:
        base_risk = RiskClassifier.classify_capability(capability)
        details = operation_details or {}

        # Escalate risk if destructive flags or system commands detected in operation details
        if details.get("destructive") or details.get("severity") in ("critical", "destructive"):
            return RiskLevel.HIGH

        return base_risk
