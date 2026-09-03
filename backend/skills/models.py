from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillLifecycleState(str, Enum):
    SAVED = "SAVED"
    INSTALLED = "INSTALLED"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    INCOMPATIBLE = "INCOMPATIBLE"
    QUARANTINED = "QUARANTINED"


class SkillTrustLevel(str, Enum):
    UNTRUSTED = "UNTRUSTED"
    COMMUNITY = "COMMUNITY"
    VERIFIED = "VERIFIED"
    CORE = "CORE"


class SkillRequirement(BaseModel):
    name: str
    version_constraint: str = "*"
    reason: Optional[str] = None


class SkillDependency(BaseModel):
    required_skills: List[SkillRequirement] = Field(default_factory=list)
    optional_skills: List[SkillRequirement] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    required_models: List[str] = Field(default_factory=list)
    supported_providers: List[str] = Field(default_factory=list)


class Skill(BaseModel):
    id: str
    name: str
    version: str
    description: str = ""
    author: str = "unknown"
    provenance: str = "local"
    checksum: Optional[str] = None
    signature: Optional[str] = None
    department: str = "general"
    category: str = "utility"
    capability: str = "skill.execute"
    tags: List[str] = Field(default_factory=list)
    dependencies: SkillDependency = Field(default_factory=SkillDependency)
    integrations: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    trust_level: SkillTrustLevel = SkillTrustLevel.UNTRUSTED
    security_status: str = "VALIDATED"
    compatibility_requirements: Dict[str, str] = Field(default_factory=dict)
    state: SkillLifecycleState = SkillLifecycleState.SAVED
    metadata: Dict[str, Any] = Field(default_factory=dict)
