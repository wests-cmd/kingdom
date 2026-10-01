from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner
from backend.skills.portable_service import PortableMapService
from backend.integrations.discord_ai_map.identity import DiscordIdentityLinker, DISCORD_GRANTS
from backend.integrations.public_apis import registry, REVIEWED, refresh_catalog

from backend.skills import portable_responses as schemas

router = APIRouter(dependencies=[Depends(require_owner)])
service = None
linker = None


def initialize(engine, lifecycle):
    global service, linker
    service = PortableMapService(engine, lifecycle, registry.repository)
    linker = DiscordIdentityLinker(service)
    for setting in service.repository.list("provider_worker"):
        if setting.get("enabled"):
            _grant_worker(setting["role"], True)


def _grant_worker(role, enabled):
    knight = service.engine.swarm.registry.get(role)
    if not knight:
        raise ValueError("Worker is not installed in this runtime profile")
    for security in (service.engine.security, knight.zero_trust):
        caps = security.nodes.get_node_capabilities(role)
        if enabled:
            caps.add("providers.test")
        else:
            caps.discard("providers.test")
        security.nodes.update_node_capabilities(role, caps)


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    filename: str = Field(max_length=110)
    content: str = Field(max_length=262144)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    preview_id: str = Field(max_length=64)
    checksum: str = Field(pattern="^[0-9a-f]{64}$")


class LinkConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str = Field(min_length=20, max_length=64)
    grants: list[str] = Field(default_factory=list, max_length=20)


class Enable(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool


class ProfilePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    profile_id: str = Field(max_length=64)
    map_id: str = Field(max_length=64)


def boundary(call):
    try:
        return call()
    except PermissionError as exc:
        safe = {"Import preview expired, changed or belongs to another identity", "Link challenge expired or already used",
                "Required Kingdom permission is not granted", "Identity is not active"}
        raise HTTPException(403, str(exc) if str(exc) in safe else "Kingdom permission or confirmation is required") from exc
    except KeyError as exc:
        raise HTTPException(404, "Record not found") from exc
    except (ValueError, TypeError) as exc:
        safe = {"No available worker has the reviewed provider-test permission", "Unknown installation profile",
                "Provider has no reviewed executable adapter", "Worker is not installed in this runtime profile",
                "Unsupported Discord permission", "No recognized catalog table; existing catalog preserved"}
        raise HTTPException(400, str(exc) if str(exc) in safe else "Invalid request; check the schema, identifier and current state") from exc
    except OSError as exc:
        raise HTTPException(503, "Public provider did not respond. Existing local records are preserved.") from exc


@router.get("/skillmaps", response_model=list[schemas.MapSummary], response_model_exclude_none=True)
def list_maps():
    return [{"map_id": row["map_id"], "checksum": row["checksum"]} for row in service.repository.list("portable_map") if row["actor"] == "owner"]


@router.get("/profiles/preferences", response_model=schemas.ProfileCatalog, response_model_exclude_none=True)
def profiles():
    return boundary(lambda: service.profiles("owner"))


@router.post("/profiles/preferences", response_model=schemas.Preference, response_model_exclude_none=True)
def profile_preferences(request: ProfilePreferences):
    return boundary(lambda: service.set_profile_preferences("owner", request.profile_id, request.map_id))


@router.post("/skillmaps/preview", response_model=schemas.MapPreview, response_model_exclude_none=True)
def preview(upload: Upload):
    return boundary(lambda: service.preview("owner", upload.filename, upload.content.encode()))


@router.post("/skillmaps/confirm", response_model=schemas.SavedMap, response_model_exclude_none=True)
def confirm(request: Confirmation):
    return boundary(lambda: service.confirm("owner", request.preview_id, request.checksum))


@router.get("/skillmaps/{map_id}/export", response_model=schemas.ExportedMap, response_model_exclude_none=True)
def export(map_id: str):
    def action():
        result = service.export("owner", map_id)
        return result | {"payload": result["payload"].decode()}
    return boundary(action)


@router.get("/skillmaps/{map_id}/download")
def download(map_id: str):
    result = boundary(lambda: service.export("owner", map_id))
    return Response(result["payload"], media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"',
                             "X-Content-SHA256": result["checksum"], "Cache-Control": "no-store"})


@router.post("/skillmaps/{map_id}/test", response_model=schemas.TestBatch, response_model_exclude_none=True)
def test_map(map_id: str):
    return boundary(lambda: service.submit_tests("owner", map_id))


@router.post("/skillmaps/{map_id}/results", response_model=schemas.TestResults, response_model_exclude_none=True)
def results(map_id: str):
    return boundary(lambda: service.collect_results("owner", map_id))


@router.get("/providers/catalog", response_model=schemas.ProviderCatalog, response_model_exclude_none=True)
def providers():
    return {"discovered": registry.catalog_entries(), "reviewed": [
        {"provider_id": pid, "capabilities": spec["capabilities"], "documentation": spec["documentation"],
         "enabled": bool((service.repository.get("provider_settings", pid) or {}).get("enabled"))} for pid, spec in REVIEWED.items()]}


@router.post("/providers/catalog/refresh", response_model=schemas.CatalogRefresh, response_model_exclude_none=True)
def refresh():
    def action():
        result = refresh_catalog()
        service.engine.events.publish("provider.catalog_refreshed", {"count": result["count"]})
        return result
    return boundary(action)


@router.post("/providers/{provider_id}/enable", response_model=schemas.ProviderSetting, response_model_exclude_none=True)
def enable_provider(provider_id: str, request: Enable):
    return boundary(lambda: service.enable_provider("owner", provider_id, request.enabled))


@router.post("/providers/workers/{role}/permission", response_model=schemas.WorkerSetting, response_model_exclude_none=True)
def worker_permission(role: str, request: Enable):
    def action():
        _grant_worker(role, request.enabled)
        service.repository.put("provider_worker", role, {"role": role, "enabled": request.enabled})
        service.engine.events.publish("provider.worker_permission_updated", {"role": role, "enabled": request.enabled})
        return {"role": role, "provider_tests_enabled": request.enabled}
    return boundary(action)


@router.get("/discord/links", response_model=schemas.DiscordLinks, response_model_exclude_none=True)
def links():
    from backend.integrations.discord_ai_map.http import adapter
    return {"links": service.repository.list("discord_link"), "available_permissions": sorted(DISCORD_GRANTS),
            "configured": bool(adapter and adapter.config.enabled), "live_connection_verified": False}


@router.post("/discord/links/confirm", response_model=schemas.DiscordLink, response_model_exclude_none=True)
def link_confirm(request: LinkConfirmation):
    return boundary(lambda: linker.confirm("owner", request.code, request.grants))


@router.post("/discord/links/{user_id}/revoke", response_model=schemas.Revocation, response_model_exclude_none=True)
def revoke(user_id: str):
    return boundary(lambda: linker.revoke("owner", user_id))
