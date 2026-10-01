import json
import asyncio
import socket
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from backend.integrations.public_apis import safe_get, PinnedHTTPSConnection
from backend.integrations.discord_ai_map.config import DiscordConfig
from backend.integrations.discord_ai_map import http
from .test_discord_skillmap_workflow import workflow


@pytest.mark.parametrize("url", ["http://example.com", "https://127.0.0.1", "https://[::1]", "https://user:pass@example.com", "https://example.com:444", "https://example.com/#fragment"])
def test_unsafe_endpoint_rejected_before_network(url):
    with pytest.raises(ValueError):
        safe_get(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "224.0.0.1", "fc00::1"])
def test_nonpublic_dns_never_connects(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (address, 443))])
    def forbidden(*args, **kwargs):
        pytest.fail("Connection must not be attempted")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    with pytest.raises(ValueError):
        PinnedHTTPSConnection("example.com").connect()


def test_mixed_public_private_dns_fails_closed(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 0, "", (address, 443)) for address in ("8.8.8.8", "127.0.0.1")])
    with pytest.raises(ValueError):
        PinnedHTTPSConnection("example.com").connect()


def test_signed_http_ping_replay_and_tamper(workflow, monkeypatch):
    service, linker = workflow
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    config = DiscordConfig(True, "987", public, "controlled-test-credential")
    monkeypatch.setattr(http, "adapter", http.DiscordAdapter(config, service, linker))
    app = FastAPI()
    app.include_router(http.router)
    client = TestClient(app)
    body = json.dumps({"application_id": "987", "id": "123", "type": 1}).encode()
    timestamp = str(int(time.time()))
    headers = {"X-Signature-Timestamp": timestamp, "X-Signature-Ed25519": key.sign(timestamp.encode() + body).hex(), "Content-Type": "application/json"}
    assert client.post("/discord/interactions", content=body, headers=headers).json() == {"type": 1}
    assert client.post("/discord/interactions", content=body, headers=headers).status_code == 409
    assert client.post("/discord/interactions", content=body + b" ", headers=headers).status_code == 401
    assert client.post("/discord/interactions", content=b"x" * 65537, headers=headers).status_code == 413


def test_discord_cannot_fetch_arbitrary_attachment(workflow):
    service, linker = workflow
    adapter = http.DiscordAdapter(DiscordConfig(True, "987"), service, linker)
    with pytest.raises(ValueError):
        adapter.download_attachment({"url": "https://127.0.0.1/private", "filename": "map.json"})


def test_malformed_timestamp_headers_fail_authentication(workflow):
    service, linker = workflow
    adapter=http.DiscordAdapter(DiscordConfig(True,'987'),service,linker)
    for timestamp in ['²','1'*5000]:
        with pytest.raises(PermissionError):
            adapter.verify('',timestamp,b'{}')


def test_busy_unhealthy_and_revoked_workers_are_ineligible(workflow):
    service, _ = workflow
    role = next(iter(service.engine.swarm.registry._knights))
    knight = service.engine.swarm.registry.get(role)
    security = knight.zero_trust.nodes
    security.update_node_capabilities(role, {"providers.test"})
    service.engine.security.nodes.update_node_capabilities(role, service.engine.security.nodes.get_node_capabilities(role) | {"providers.test"})
    assert role in service.compatible_knights()
    service.engine.swarm.registry.begin(role)
    assert role not in service.compatible_knights()
    service.engine.swarm.registry.finish(role)
    knight.health = "unhealthy"
    assert role not in service.compatible_knights()
    knight.health = "healthy"
    security.revoke_node(role)
    assert role not in service.compatible_knights()


def test_signed_command_is_acknowledged_before_command_work(workflow, monkeypatch):
    service, linker = workflow
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    adapter = http.DiscordAdapter(DiscordConfig(True, "987", public, "controlled-test-credential"), service, linker)
    received = []
    async def deliver(interaction):
        received.append(interaction["data"]["name"])
    monkeypatch.setattr(adapter, "deliver_interaction", deliver)
    monkeypatch.setattr(http, "adapter", adapter)
    app = FastAPI()
    app.include_router(http.router)
    body = json.dumps({"application_id":"987", "id":"124", "type":2, "data":{"name":"help"}}).encode()
    timestamp = str(int(time.time()))
    headers = {"X-Signature-Timestamp":timestamp,"X-Signature-Ed25519":key.sign(timestamp.encode()+body).hex()}
    response = TestClient(app).post('/discord/interactions',content=body,headers=headers)
    assert response.json() == {"type":5,"data":{"flags":64}}
    assert received == ["help"]


def test_export_attachment_delivery_uses_canonical_bytes_without_test_grant(workflow, monkeypatch):
    from .test_discord_skillmap_workflow import import_map
    from backend.integrations.discord_ai_map import adapter as adapter_module
    from backend.skills.portable import parse_map, canonical_map
    service, linker = workflow
    code = linker.challenge('123')['code']
    actor = linker.confirm('owner',code,['import_skillmaps','export_skillmaps'])['actor']
    import_map(service,actor)
    captured = []
    class Client:
        def __init__(self,**kwargs):
            assert kwargs['follow_redirects'] is False
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,**kwargs):
            captured.append((url,kwargs))
            return type('Response',(),{'status_code':200})()
    monkeypatch.setattr(adapter_module.httpx,'AsyncClient',Client)
    adapter = http.DiscordAdapter(DiscordConfig(True,'987'),service,linker)
    asyncio.run(adapter.deliver_deferred({'token':'controlled-test-token'}, {'deferred':'export','actor':actor,'map_id':'product-research'}))
    url, kwargs = captured[0]
    assert url == 'https://discord.com/api/v10/webhooks/987/controlled-test-token'
    payload = json.loads(kwargs['data']['payload_json'])
    assert payload['flags'] == 64 and payload['allowed_mentions'] == {'parse':[]}
    filename, content, mime = kwargs['files']['files[0]']
    assert mime == 'application/json'
    assert canonical_map(parse_map(filename,content)) == content
    assert service.repository.list('map_test') == []


def test_discord_import_preview_button_confirmation_and_export(workflow, monkeypatch):
    from .test_discord_skillmap_workflow import FIXTURE
    from backend.integrations.discord_ai_map import adapter as adapter_module
    service, linker = workflow
    challenge=linker.challenge('123')
    actor=linker.confirm('owner',challenge['code'],['import_skillmaps','export_skillmaps'])['actor']
    captured=[]
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,**kwargs):
            captured.append(kwargs)
            return type('Response',(),{'status_code':200})()
    monkeypatch.setattr(adapter_module.httpx,'AsyncClient',Client)
    adapter=http.DiscordAdapter(DiscordConfig(True,'987'),service,linker)
    monkeypatch.setattr(adapter,'download_attachment',lambda attachment: FIXTURE.read_bytes())
    interaction={'application_id':'987','type':2,'user':{'id':'123'},'token':'controlled-test-token',
                 'data':{'name':'skillmap','options':[{'name':'import','options':[{'name':'file','value':'456'}]}],
                         'resolved':{'attachments':{'456':{'filename':FIXTURE.name,'size':FIXTURE.stat().st_size,
                                                         'url':'https://cdn.discordapp.com/attachments/123/456/map.json'}}}}}
    asyncio.run(adapter.deliver_interaction(interaction))
    preview=captured[-1]['json']
    assert '1 unsupported' in preview['content'] and preview['flags']==64
    assert service.repository.list('portable_map')==[]
    custom_id=preview['components'][0]['components'][0]['custom_id']
    confirmation=interaction | {'type':3,'data':{'custom_id':custom_id}}
    asyncio.run(adapter.deliver_interaction(confirmation))
    assert service.get(actor,'product-research').providers[0].provider_id=='openfoodfacts'
    assert service.lifecycle.skills=={}
    asyncio.run(adapter.deliver_interaction(interaction | {'data':{'name':'skillmap','options':[{'name':'export','options':[{'name':'map_id','value':'product-research'}]}]}}))
    assert captured[-1]['files']['files[0]'][1] == service.export(actor,'product-research')['payload']
