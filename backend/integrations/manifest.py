"""
Kingdom Integration Manifest & Schema Validator.
Defines canonical integration manifests, risk classifications, protocol versions, and schema checks.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional

class IntegrationRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IntegrationLifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    INSTALLED = "INSTALLED"
    AUTHENTICATED = "AUTHENTICATED"
    VERIFIED = "VERIFIED"
    ENABLED = "ENABLED"
    HEALTHY = "HEALTHY"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    QUARANTINED = "QUARANTINED"
    REVOKED = "REVOKED"

@dataclass
class IntegrationManifest:
    integration_id: str
    name: str
    version: str
    publisher: str
    protocol_version: str
    description: str
    capabilities: List[str]
    permissions: List[str]
    tools: List[str]
    risk_level: IntegrationRiskLevel
    data_classification: str
    authoritative: bool = False
    dependencies: List[str] = field(default_factory=list)
    configuration_schema: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        errors = []
        if not self.integration_id or "." not in self.integration_id:
            errors.append("integration_id must be reverse-domain formatted (e.g. org.kingdom.github)")
        if not self.name:
            errors.append("name is required")
        if not self.version:
            errors.append("version is required")
        if self.protocol_version != "1.0":
            errors.append(f"unsupported protocol_version: {self.protocol_version}")
        if not self.capabilities:
            errors.append("at least one capability must be declared")
        return errors
