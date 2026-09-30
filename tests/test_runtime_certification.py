"""Release blockers verified with real authentication and durable SQLite state."""
from concurrent.futures import ThreadPoolExecutor
import time
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from backend.main import app
from backend.security.http_auth import owner_auth
from backend.security.approval_engine import ApprovalEngine
from backend.security.zero_trust import ZeroTrust
from backend.storage.db import Database
from backend.storage.repository import TaskRepository
from backend.runtime.tasks import TaskManager
from backend.runtime.execution import execute_request, verify_request_result
from backend.cluster.task_leasing import TaskLeaseManager
from backend.memory.service import MemoryService
from tests.auth_support import owner_client

@pytest.mark.parametrize("method,path,body", [("POST","/start",None), ("GET","/security/permissions",None),
    ("POST","/nodes/invitation",None), ("POST","/security/approvals/missing/approve",{}),
    ("POST","/skills/missing/activate",None), ("POST","/tasks",{"prompt":"hello"})])
def test_control_plane_requires_authentication(method, path, body):
    response = TestClient(app).request(method, path, json=body)
    assert response.status_code in {401,403}


def test_cookie_mutation_requires_request_header_and_same_origin():
    client = owner_client(app)
    client.headers.pop("Authorization")
    assert client.post("/mode", json={"mode":"adaptive"}).status_code in {403,405}
    assert client.put("/mode", json={"mode":"adaptive"}).status_code == 403
    assert client.put("/mode", json={"mode":"adaptive"}, headers={"X-Kingdom-Request":"1", "Origin":"https://attacker.invalid"}).status_code == 403
    assert client.put("/mode", json={"mode":"adaptive"}, headers={"X-Kingdom-Request":"1"}).status_code == 200
    with pytest.raises(WebSocketDisconnect):
        with TestClient(app).websocket_connect("/ws"):
            pass


def test_owner_cannot_impersonate_other_actor_or_expose_tokens():
    client = owner_client(app)
    assert client.post("/tasks", json={"prompt":"hello","metadata":{"actor":"admin"}}).status_code == 403
    assert client.post("/security/authorize", json={"actor_id":"admin","capability":"memory.read","operation":"read"}).status_code == 403
    assert owner_auth.token not in client.get("/security/permissions").text
    assert client.post("/skills/missing/activate?governance_approved=true").status_code == 403


def test_approvals_survive_restart_bind_exact_scope_and_are_spent_once(tmp_path):
    database = Database(tmp_path / "state.db")
    original = ApprovalEngine(database=database)
    req = original.create_request(capability="process.execute", operation="one operation", requesting_actor="owner", parameters={"task_id":"task-a","path":"a"})
    original.approve(req["id"], approver="owner")
    reopened = ApprovalEngine(database=database)
    scope = dict(actor_id="owner", capability="process.execute", operation="one operation", parameters={"task_id":"task-a","path":"a"})
    assert not reopened.consume(req["id"], **{**scope, "operation":"different operation"})
    assert not reopened.consume(req["id"], **{**scope, "parameters":{"task_id":"task-b","path":"a"}})
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: ApprovalEngine(database=database).consume(req["id"], **scope), range(4)))
    assert results.count(True) == 1
    assert ApprovalEngine(database=database).get_request(req["id"])["status"] == "consumed"
    with pytest.raises(ValueError):
        reopened.approve(req["id"])


def test_approved_request_expires_before_use(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    import backend.security.approval_engine as approval_module
    approvals = ApprovalEngine(default_ttl_seconds=3600, database=Database(tmp_path / "state.db"))
    req = approvals.create_request("process.execute", "execute", requesting_actor="owner")
    approvals.approve(req["id"], approver="owner")
    class ExpiredClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(seconds=3601)
    monkeypatch.setattr(approval_module, "datetime", ExpiredClock)
    assert not approvals.consume(req["id"], actor_id="owner", capability="process.execute", operation="execute", parameters={})
    assert approvals.get_request(req["id"])["status"] == "expired"


def test_pure_execution_is_real_and_tampered_result_is_rejected():
    task = {"id":"verified-task","prompt":"three real words", "metadata":{"tool":"text.analyze@1.0.0"}}
    result = execute_request(task, {"compute"})
    assert result["output"]["words"] == 3
    assert verify_request_result(task, result)["state"] == "VERIFIED"
    result["output"]["words"] = 500
    with pytest.raises(ValueError, match="verification rejected"):
        verify_request_result(task, result)
    with pytest.raises(PermissionError):
        execute_request(task, set())


def test_claim_race_cannot_create_second_active_lease(tmp_path):
    database = Database(tmp_path / "state.db")
    tasks = TaskManager(TaskRepository(database))
    task = tasks.create("three real words", {"execution_target":"remote","tool":"text.analyze@1.0.0"})
    def claim(worker):
        return TaskLeaseManager(database=database).issue_and_claim(task["id"], worker, "compute", 1)
    with ThreadPoolExecutor(2) as pool:
        claims = list(pool.map(claim, ["worker-a","worker-b"]))
    assert sum(c is not None for c in claims) == 1
    winner = next(c for c in claims if c)
    reopened = TaskLeaseManager(database=database)
    assert reopened.validate_lease_execution(task["id"], winner.assigned_node_id, winner.fencing_token)
    with pytest.raises(PermissionError):
        reopened.validate_lease_execution(task["id"], winner.assigned_node_id, winner.fencing_token + 1)
    reopened.revoke_lease(task["id"])
    assert TaskLeaseManager(database=database).issue_lease(task["id"], "next-worker", "compute").fencing_token == winner.fencing_token + 1


def test_all_tasks_restore_and_stale_terminal_write_cannot_override(tmp_path):
    repository = TaskRepository(Database(tmp_path / "state.db"))
    tasks = TaskManager(repository)
    for n in range(505):
        tasks.create(str(n))
    reopened = TaskManager(repository)
    assert len(reopened.list()) == 505
    task = tasks.claim_next()
    changed = repository.get(task["id"])
    changed.update(status="RECOVERY_REQUIRED", version=changed["version"]+1)
    repository.save(changed, expected_version=task["version"])
    with pytest.raises(ValueError, match="stale write"):
        tasks.complete(task["id"], {"invented":"result"})
    assert repository.get(task["id"])["status"] == "RECOVERY_REQUIRED"


def test_memory_concurrent_instances_preserve_both_entries(tmp_path):
    first = MemoryService(tmp_path)
    second = MemoryService(tmp_path)
    first.add("first real entry")
    second.add("second real entry")
    assert len(MemoryService(tmp_path).entries()) == 2


def test_claimed_identity_without_credentials_is_denied():
    security = ZeroTrust()
    assert security.authorize("admin", "memory.read", "read")["authorized"] is False
    assert security.validate({"id":"admin","verified":True})["trusted"] is False
