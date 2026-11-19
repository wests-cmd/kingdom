"""Truthful, owner-only adapter inventory; no credentials or side effects."""
import json
import sqlite3

from fastapi.testclient import TestClient
from tests.auth_support import owner_client
from backend.main import app
from backend.integrations.acp_adapters import ACPToolManager, is_local_endpoint


class ReadOnlyDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
    def get_connection(self):
        class Context:
            def __init__(self, conn): self.conn = conn
            def __enter__(self): return self.conn
            def __exit__(self, typ, val, tb): return False
        return Context(self.conn)


def test_adapter_presence_is_never_execution_authority(monkeypatch):
    monkeypatch.setattr("backend.integrations.acp_adapters.shutil.which", lambda exe: "/bin/" + exe)
    tools = ACPToolManager().list_tools()
    assert len(tools) == 5
    assert all(tool["installed"] and not tool["connected"] and not tool["authenticated"]
               and not tool["available_to_planner"] and not tool["acp_compliant"]
               and not tool["granted_execution_authority"] for tool in tools)


def test_configured_models_remain_unverified_and_discovery_is_read_only():
    db = ReadOnlyDB()
    with db.get_connection() as conn:
        conn.execute("CREATE TABLE model_profiles(id TEXT PRIMARY KEY, config_json TEXT NOT NULL, secret BLOB)")
        conn.execute("INSERT INTO model_profiles VALUES(?,?,?)",
                     ("saved", json.dumps({"model": "local-demo", "provider": "ollama",
                                         "endpoint": "http://127.0.0.1:11434", "num_ctx": 2048}), b"SECRET"))
        conn.execute("CREATE TABLE chatgpt_plan_meta(id INTEGER PRIMARY KEY,value_json TEXT NOT NULL)")
        conn.execute("INSERT INTO chatgpt_plan_meta VALUES(1,?)",
                     (json.dumps({"enabled": True, "model": "configured-demo"}),))
        conn.commit()
        before = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    inventory = ACPToolManager(db=db).list_models()
    assert {m["name"] for m in inventory} == {"local-demo", "configured-demo"}
    assert all(m["available"] is False for m in inventory)
    assert "SECRET" not in str(inventory)
    with db.get_connection() as conn:
        after = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    assert before == after


def test_empty_discovery_creates_no_tables():
    db = ReadOnlyDB()
    assert ACPToolManager(db=db).list_models() == []
    with db.get_connection() as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


def test_endpoint_classification_does_not_trust_similar_remote_hostname():
    assert is_local_endpoint("https://localhost.evil.example") is False
    assert is_local_endpoint("http://localhost:11434") is True
    assert is_local_endpoint("http://127.0.0.1:11434") is True
    assert is_local_endpoint("http://[::1]:11434") is True


def test_adapter_routes_owner_only_and_do_not_claim_ready():
    assert TestClient(app).get("/integrations/adapters").status_code in (401, 403)
    response = owner_client(app).get("/integrations/adapters")
    assert response.status_code == 200
    data = response.json()
    assert data["execution_authority_granted"] is False
    assert all(not tool["available_to_planner"] for tool in data["tools"])
    assert owner_client(app).get("/integrations/adapters/not-present").status_code == 404
