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
    assert status["activity"] == "Processing a task"
    assert status["capabilities"] == ["model.inference"]
    registry.finish("coder")
    assert registry.status()[0]["status"] == "ready"
