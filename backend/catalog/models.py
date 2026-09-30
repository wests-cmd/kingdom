"""
Pydantic Models for Profiles, Capabilities, API Providers, Mappings, and Catalog Operations.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import time


class Capability(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    category: str
    risk_level: str = "low"  # low, medium, high, critical
    requires_auth: bool = False
    requires_approval: bool = False
    read_only: bool = True
    enabled: bool = True
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class Profile(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    icon: Optional[str] = "zap"
    system: bool = False
    status: str = "active"  # active, inactive, draft
    version: int = 1
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ProfileCapability(BaseModel):
    profile_id: str
    capability_id: str
    priority: int = 0
    required: bool = False
    mode: str = "recommend"  # recommend, preferred, required
    created_at: float = Field(default_factory=time.time)


class UserProfile(BaseModel):
    id: str
    user_id: str = "default_user"
    profile_id: str
    name: str
    enabled: bool = True
    is_default: bool = False
    preferences_json: Optional[Dict[str, Any]] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ApiProvider(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    homepage_url: Optional[str] = None
    documentation_url: Optional[str] = None
    source: str = "public_apis"
    category: Optional[str] = "General"
    auth_type: str = "none"  # none, api_key, oauth, user_agent, unknown
    https_supported: bool = True
    cors_support: str = "unknown"  # yes, no, unknown
    free_access: str = "unknown"  # no_auth, free, free_tier, credentials_required, paid, unknown
    status: str = "discovered"  # discovered, verified, degraded, unreachable, disabled
    last_verified_at: Optional[float] = None
    verification_status: str = "unverified"  # unverified, verified, failed
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ApiCapability(BaseModel):
    api_provider_id: str
    capability_id: str
    confidence: float = 1.0
    mapping_source: str = "catalog"
    verified: bool = False
    created_at: float = Field(default_factory=time.time)


class CatalogSyncRecord(BaseModel):
    id: str
    source: str
    started_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    entries_seen: int = 0
    entries_added: int = 0
    entries_updated: int = 0
    entries_disabled: int = 0
    errors: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    source_checksum: Optional[str] = None


class ApiVerificationRecord(BaseModel):
    id: str
    api_provider_id: str
    checked_at: float = Field(default_factory=time.time)
    reachable: bool = False
    https_valid: bool = False
    documentation_reachable: bool = False
    auth_detected: Optional[str] = None
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
