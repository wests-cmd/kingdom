import pytest
import time
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.sync_engine import sync_engine
from backend.learning.hypothesis import hypothesis_engine

def test_unannounced_node_disappearance_and_task_reassignment():
    # Register an active worker executing task-999
    node_id = "kn-disappear-01"
    node_registry.register_discovered_node({
        "id": node_id,
        "node_state": NodeState.CONNECTED.value,
        "hardware_profile": {"cpu_cores": 8, "vram_mb": 16384},
        "software_version": "40.2.0"
    })

    # Simulate node claiming task-999 and then missing heartbeats
    node = node_registry.get_node(node_id)
    node["current_task"] = "task-999"
    node["last_heartbeat"] = time.time() - 120.0 # Timeout 2 minutes ago
    node_registry.repo.save(node)

    # Check stale heartbeats
    node_registry.check_stale_heartbeats(timeout_seconds=60.0)

    # Verify node marked DISCONNECTED and active task cleared
    updated = node_registry.get_node(node_id)
    assert updated["node_state"] == NodeState.DISCONNECTED.value
    assert updated["health"] == "unhealthy"
    assert updated["current_task"] is None

def test_deterministic_sync_engine_conflict_resolution():
    node_id = "kn-sync-01"
    now = time.time()

    # Save local node state at t=100
    node_registry.register_discovered_node({
        "id": node_id,
        "node_state": NodeState.CONNECTED.value,
        "status": "idle"
    })

    # Prepare newer remote state at t=200
    remote_state = [{
        "id": node_id,
        "node_state": NodeState.CONNECTED.value,
        "status": "busy",
        "health": "healthy",
        "updated_at": now + 100.0
    }]

    # Sync and reconcile
    res = sync_engine.synchronize(remote_state=remote_state)
    assert res["status"] == "synced"
    assert res["reconciled_nodes"] == 1

    # Verify local node state updated to newer remote status
    reconciled = node_registry.get_node(node_id)
    assert reconciled["status"] == "busy"

def test_multi_metric_hypothesis_sandbox_gating():
    # Generate optimization hypothesis
    hyp = hypothesis_engine.generate_hypothesis(
        subsystem="OCR",
        observation="Heavy OCR latency spike on scanned documents",
        proposed_optimization="Route small document snippets to lightweight OCR model"
    )

    # 1. Benchmark fails due to accuracy drop -> REJECTED
    res_fail = hypothesis_engine.evaluate_hypothesis_in_sandbox(hyp.id, {
        "latency_delta_pct": -20.0,
        "accuracy_delta_pct": -5.0, # Accuracy dropped!
        "security_violations": 0
    })
    assert res_fail["success"] is False
    assert res_fail["status"] == "REJECTED"

    # 2. Benchmark succeeds on all metrics -> VALIDATED
    hyp_ok = hypothesis_engine.generate_hypothesis(
        subsystem="OCR_V2",
        observation="Parallelized image preprocessing",
        proposed_optimization="Use multi-threaded canvas resize"
    )
    res_pass = hypothesis_engine.evaluate_hypothesis_in_sandbox(hyp_ok.id, {
        "latency_delta_pct": -18.0,
        "accuracy_delta_pct": 0.0,
        "security_violations": 0
    })
    assert res_pass["success"] is True
    assert res_pass["status"] == "VALIDATED"
