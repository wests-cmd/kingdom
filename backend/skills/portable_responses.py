"""Typed public integration responses; never serialize arbitrary internal records."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
from backend.skills.portable import ProviderEvidence


class PublicResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MapSummary(PublicResponse):
    map_id: str
    checksum: str


class SavedMap(MapSummary):
    state: Literal['saved_preferences']


class ExportedMap(PublicResponse):
    filename: str
    payload: str
    checksum: str


class PreviewProvider(PublicResponse):
    provider_id: str
    reviewed: bool
    credential_required: bool
    requested_capabilities: list[str]
    supported_capabilities: list[str]


class MapPreview(MapSummary):
    preview_id: str
    skills: int
    understood_skills: list[str]
    unsupported_skills: list[str]
    understood_capabilities: list[str]
    unsupported_capabilities: list[str]
    providers: list[PreviewProvider]
    compatible_knights: list[str]
    notice: str


class Profile(PublicResponse):
    profile_id: str
    name: str
    knights: list[str]


class Preference(PublicResponse):
    actor: str
    profile_id: str
    map_id: str


class ProfileCatalog(PublicResponse):
    available: list[Profile]
    preferences: Preference | None
    notice: str


class TaskEvidence(PublicResponse):
    task_id: str
    provider_id: str
    status: str


class SkippedProvider(PublicResponse):
    provider_id: str
    status: Literal['disabled', 'unsupported']


class TestBatch(PublicResponse):
    tasks: list[TaskEvidence]
    skipped: list[SkippedProvider]
    notice: str


class TestResults(PublicResponse):
    tasks: list[TaskEvidence]
    results: list[ProviderEvidence]
    notice: str


class DiscoveredProvider(PublicResponse):
    provider_id: str
    name: str
    category: str
    documentation: str
    authentication: Literal['none', 'required']
    https_claimed: bool
    cors_claim: str
    source: Literal['public-apis/public-apis']
    state: Literal['discovered']
    executable: Literal[False]


class ReviewedProvider(PublicResponse):
    provider_id: str
    capabilities: list[str]
    documentation: str
    enabled: bool


class ProviderCatalog(PublicResponse):
    discovered: list[DiscoveredProvider]
    reviewed: list[ReviewedProvider]


class CatalogRefresh(PublicResponse):
    count: int
    sha256: str
    source: str


class ProviderSetting(PublicResponse):
    provider_id: str
    enabled: bool


class WorkerSetting(PublicResponse):
    role: str
    provider_tests_enabled: bool


class DiscordLink(PublicResponse):
    user_id: str
    actor: str
    grants: list[str]
    revoked: bool


class DiscordLinks(PublicResponse):
    links: list[DiscordLink]
    available_permissions: list[str]
    configured: bool
    live_connection_verified: Literal[False]


class Revocation(PublicResponse):
    state: Literal['revoked']


class AllowedMentions(PublicResponse):
    parse: list[str]


class InteractionData(PublicResponse):
    flags: Literal[64]
    content: str | None = None
    allowed_mentions: AllowedMentions | None = None


class InitialInteractionResponse(PublicResponse):
    type: Literal[1, 4, 5]
    data: InteractionData | None = None
