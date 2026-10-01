import asyncio
import json
import time
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from backend.runtime.engine import RuntimeEngine
from backend.runtime.tasks import TaskManager
from backend.runtime.policy import ExecutionPolicy
from backend.storage.db import Database
from backend.storage.repository import TaskRepository
from backend.storage.integration_repository import IntegrationRepository
from backend.skills.lifecycle import SkillLifecycleManager
from backend.skills.portable_service import PortableMapService
from backend.integrations.provider import ProviderRegistry
from backend.integrations import public_apis
from backend.integrations.discord_ai_map.identity import DiscordIdentityLinker
from backend.integrations.discord_ai_map.config import DiscordConfig
from backend.integrations.discord_ai_map.adapter import DiscordAdapter

FIXTURE = Path(__file__).parents[1] / "fixtures/product-research.skillmap.json"


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    database = Database(tmp_path / "kingdom.db")
    repository = IntegrationRepository(database)
    engine = RuntimeEngine()
    engine.tasks = TaskManager(TaskRepository(database))
    engine.execution_policy = ExecutionPolicy(database)
    service = PortableMapService(engine, SkillLifecycleManager(), repository)
    monkeypatch.setattr(public_apis, "registry", ProviderRegistry(repository))
    return service, DiscordIdentityLinker(service)


def import_map(service, actor="owner"):
    preview = service.preview(actor, FIXTURE.name, FIXTURE.read_bytes())
    service.confirm(actor, preview["preview_id"], preview["checksum"])
    return preview


def test_resource_preference_never_grants_worker_authority(workflow):
    service, _ = workflow
    import_map(service)
    for role in ['planner','researcher']:
        worker=service.engine.swarm.registry.get(role)
        for security in [service.engine.security,worker.zero_trust]:
            security.nodes.update_node_capabilities(role,security.nodes.get_node_capabilities(role)|{'providers.test'})
    service.enable_provider('owner','openfoodfacts',True)
    submitted=service.submit_tests('owner','product-research')
    assert service.engine.tasks.get(submitted['tasks'][0]['task_id'])['metadata']['requested_knight']=='researcher'
    service.engine.security.nodes.revoke_node('researcher')
    submitted=service.submit_tests('owner','product-research')
    assert service.engine.tasks.get(submitted['tasks'][0]['task_id'])['metadata']['requested_knight']=='planner'


def test_saved_profile_preference_ranks_only_installed_authorized_workers(workflow):
    service, _ = workflow
    data=json.loads(FIXTURE.read_text(encoding='utf-8'));data['preferred_resources']=[]
    preview=service.preview('owner',FIXTURE.name,json.dumps(data).encode())
    service.confirm('owner',preview['preview_id'],preview['checksum'])
    for role in ['coder','memory']:
        worker=service.engine.swarm.registry.get(role)
        for security in [service.engine.security,worker.zero_trust]:
            security.nodes.update_node_capabilities(role,security.nodes.get_node_capabilities(role)|{'providers.test'})
    assert service.preferred_knights('owner',service.get('owner','product-research'))==['coder','memory']
    service.set_profile_preferences('owner','research','product-research')
    assert service.preferred_knights('owner',service.get('owner','product-research'))==['memory','coder']
    assert service.engine.swarm.registry.get('researcher').zero_trust.nodes.get_node_capabilities('researcher').isdisjoint({'providers.test'})


def test_explicit_link_grants_revocation_and_restart(workflow):
    service, linker = workflow
    with pytest.raises(PermissionError):
        linker.actor("123")
    challenge = linker.challenge("123")
    link = linker.confirm("owner", challenge["code"], ["view_status"])
    service.authorize(link["actor"], "view_status")
    with pytest.raises(PermissionError):
        service.authorize(link["actor"], "run_task")
    with pytest.raises(PermissionError):
        linker.confirm("owner", challenge["code"], ["view_status"])
    DiscordIdentityLinker(service)
    service.authorize(link["actor"], "view_status")
    linker.revoke("owner", "123")
    with pytest.raises(PermissionError):
        linker.actor("123")
    with pytest.raises(PermissionError):
        service.authorize(link["actor"], "view_status")


def test_guild_admin_does_not_authorize_kingdom(workflow):
    service, linker = workflow
    adapter = DiscordAdapter(DiscordConfig(True, "987"), service, linker)
    with pytest.raises(PermissionError):
        adapter.route({"application_id": "987", "type": 2, "member": {"user": {"id": "123"}, "permissions": "8"}, "data": {"name": "status"}})


def test_link_expiry_and_escalation_denied(workflow):
    service, linker = workflow
    challenge = linker.challenge("123")
    with pytest.raises(ValueError):
        linker.confirm("owner", challenge["code"], ["system.admin"])
    import hashlib
    key = hashlib.sha256(challenge["code"].encode()).hexdigest()
    record = service.repository.get("discord_challenge", key)
    record["expires_at"] = 0
    service.repository.put("discord_challenge", key, record)
    with pytest.raises(PermissionError):
        linker.confirm("owner", challenge["code"], [])


def test_preview_identity_checksum_expiry_and_single_use(workflow):
    service, linker = workflow
    preview = service.preview("owner", FIXTURE.name, FIXTURE.read_bytes())
    assert preview["unsupported_skills"] == ["product-research"]
    assert not preview["compatible_knights"]
    with pytest.raises(PermissionError):
        service.confirm("owner", preview["preview_id"], "0" * 64)
    service.confirm("owner", preview["preview_id"], preview["checksum"])
    with pytest.raises(PermissionError):
        service.confirm("owner", preview["preview_id"], preview["checksum"])
    exported = service.export("owner", "product-research")
    assert exported["checksum"] == preview["checksum"]
    reimport = service.preview("owner", exported["filename"], exported["payload"])
    assert reimport["checksum"] == exported["checksum"]
    assert service.lifecycle.skills == {}  # Import has not installed code or promoted trust.


def test_signed_requests_tamper_and_stale_rejected(workflow):
    service, linker = workflow
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    adapter = DiscordAdapter(DiscordConfig(True, "987", public), service, linker)
    timestamp = str(int(time.time()))
    body = b'{"type":1}'
    signature = key.sign(timestamp.encode() + body).hex()
    adapter.verify(signature, timestamp, body)
    with pytest.raises(PermissionError):
        adapter.verify(signature, timestamp, b'{"type":2}')
    with pytest.raises(PermissionError):
        adapter.verify(signature, "1", body)


def test_provider_get_runs_through_governed_knight_and_roundtrips(workflow, monkeypatch):
    service, _ = workflow
    import_map(service)
    role = next(iter(service.engine.swarm.registry._knights))
    knight = service.engine.swarm.registry.get(role)
    for security in (service.engine.security, knight.zero_trust):
        caps = security.nodes.get_node_capabilities(role)
        security.nodes.update_node_capabilities(role, caps | {"providers.test"})
    service.repository.put("provider_settings", "openfoodfacts", {"enabled": True})
    monkeypatch.setattr(public_apis, "safe_get", lambda *args, **kwargs: (b'{"code":"3017620422003","status":1,"product":{"product_name":"Nutella"}}', "application/json"))
    submitted = service.submit_tests("owner", "product-research")
    assert len(submitted["tasks"]) == 1
    asyncio.run(service.engine._process_next_task())
    task = service.engine.tasks.get(submitted["tasks"][0]["task_id"])
    assert task["status"] == "completed", task.get("error")
    evidence = service.collect_results("owner", "product-research")
    assert evidence["results"][0]["status"] == "verified"
    exported = service.export("owner", "product-research")
    preview = service.preview("owner", exported["filename"], exported["payload"])
    assert preview["checksum"] == exported["checksum"]
    # Independently reject a changed response instead of trusting a Knight's success flag.
    from backend.runtime.execution import verify_request_result
    outcome = task["result"]["results"][0]["outcome"]
    outcome["output"]["body"] = '{"code":"3017620422003","status":1,"product":{"product_name":"Changed"}}'
    with pytest.raises(ValueError):
        verify_request_result(task, outcome)


@pytest.mark.parametrize("failure", ["timeout", "malformed", "schema", "mime"])
def test_provider_failures_are_not_verified(workflow, monkeypatch, failure):
    service, _ = workflow
    import_map(service)
    role = next(iter(service.engine.swarm.registry._knights))
    knight = service.engine.swarm.registry.get(role)
    for security in (service.engine.security, knight.zero_trust):
        security.nodes.update_node_capabilities(role, security.nodes.get_node_capabilities(role) | {"providers.test"})
    service.repository.put("provider_settings", "openfoodfacts", {"enabled": True})
    def response(*args, **kwargs):
        if failure == "timeout":
            raise TimeoutError("Controlled provider timeout")
        return {"malformed": (b"{", "application/json"), "schema": (b"{}", "application/json"),
                "mime": (b"{}", "text/html")}[failure]
    monkeypatch.setattr(public_apis, "safe_get", response)
    submitted = service.submit_tests("owner", "product-research")
    asyncio.run(service.engine._process_next_task())
    task = service.engine.tasks.get(submitted["tasks"][0]["task_id"])
    assert task["status"] == "failed"
    assert service.collect_results("owner", "product-research")["results"][0]["status"] == "failed"


def test_missing_credentials_fail_safe(monkeypatch):
    monkeypatch.setenv("KINGDOM_DISCORD_ENABLED", "true")
    for field in ("APPLICATION_ID", "PUBLIC_KEY", "BOT_TOKEN"):
        monkeypatch.delenv("KINGDOM_DISCORD_" + field, raising=False)
    with pytest.raises(ValueError, match="incomplete"):
        DiscordConfig.from_environment()


def test_catalog_is_discovery_and_not_a_network_executor():
    markdown = "### Shopping\n| API | Description | Auth | HTTPS | CORS |\n|---|---|---|---|---|\n| [Example](https://example.com/docs) | products | apiKey | Yes | Unknown |"
    entries = public_apis.parse_catalog(markdown)
    assert entries[0]["authentication"] == "required"
    assert entries[0]["executable"] is False
    assert entries[0]["state"] == "discovered"
    with pytest.raises(ValueError):
        public_apis.probe_provider(entries[0]["provider_id"])
