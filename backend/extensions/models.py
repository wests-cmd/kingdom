import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtensionTrustState(str, Enum):
    DISCOVERED = "DISCOVERED"
    INSTALLED = "INSTALLED"
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"
    QUARANTINED = "QUARANTINED"
    REVOKED = "REVOKED"


class ExtensionToolDeclaration(BaseModel):
    tool_id: str
    name: str
    description: str
    version: str = "1.0.0"
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    required_permissions: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL


class ExtensionManifest(BaseModel):
    extension_id: str
    name: str
    version: str
    description: str
    author: str
    kingdom_compatibility: str = ">=40.0.0"
    capabilities: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    dependencies: Dict[str, str] = Field(default_factory=dict)
    configuration_schema: Dict[str, Any] = Field(default_factory=dict)
    healthcheck_endpoint: Optional[str] = None
    subscribed_events: List[str] = Field(default_factory=list)
    tools: List[ExtensionToolDeclaration] = Field(default_factory=list)
    entrypoint: str = "index.py"
    signature: Optional[str] = None


class ExtensionInstance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    manifest: ExtensionManifest
    state: ExtensionTrustState = ExtensionTrustState.DISCOVERED
    installed_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    config: Dict[str, Any] = Field(default_factory=dict)
    error_count: int = 0
    last_error: Optional[str] = None
    last_healthcheck_passed: bool = True
