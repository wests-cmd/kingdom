from backend.knights.registry import KnightRegistry


def test_runtime_source_and_credentials_never_become_worker_labels():
    registry = KnightRegistry(["coder"])
    worker = registry.get("coder")
    source = 'def execute(): return "secret-token"'
    worker.current_task = source
    worker.health = source
    worker.capabilities = [source, "model.inference"]
    worker.role = source
    registry.begin("coder")
    status = registry.status()[0]
    assert source not in str(status)
    assert "secret-token" not in str(status)
    assert status["current_task"] is None
    assert status["health"] == "unknown"
    assert status["activity"] == "Health unavailable"
    assert set(status["capabilities"]) == {"model.inference","memory.read","compute"}
    registry.finish("coder")
    worker.health = 'healthy'
    assert registry.status()[0]["status"] == "ready"


def test_advertised_permissions_require_current_grants_in_both_layers():
    from backend.security.zero_trust import ZeroTrust
    security = ZeroTrust()
    registry = KnightRegistry(['coder'],security=security)
    worker = registry.get('coder')
    worker.zero_trust.nodes.update_node_capabilities('coder',{'compute','providers.test'})
    security.nodes.update_node_capabilities('coder',{'compute'})
    assert registry.status()[0]['capabilities'] == ['compute']
    security.nodes.update_node_capabilities('coder',{'compute','providers.test'})
    assert registry.status()[0]['capabilities'] == ['compute','providers.test']
    security.nodes.revoke_node('coder')
    assert registry.status()[0]['capabilities'] == []
    assert registry.status()[0]['status'] == 'offline'
