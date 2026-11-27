"""Real SQLite admission races: no stale dispatcher can overwrite retained work."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.runtime.tasks import TaskManager
from backend.storage.db import Database
from backend.storage.repository import TaskRepository


def managers(tmp_path):
    db = Database(tmp_path / "admission.db")
    return TaskManager(TaskRepository(db)), TaskManager(TaskRepository(db))


def metadata():
    return {"_mission_step_key": "mission:1:step", "mission_id": "mission",
            "mission_version": 1, "step_id": "step", "actor": "owner",
            "tool": "text.analyze@1.0.0", "tool_parameters": {"text": "approved"}}


def test_competing_dispatchers_admit_only_one_execution(tmp_path):
    first, second = managers(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda manager: manager.create("approved", metadata()),
                             [first, second]))
    assert rows[0]["id"] == rows[1]["id"]
    assert rows[0]["execution_id"] == rows[1]["execution_id"]
    assert len(first.repo.list_all()) == 1
    assert first.claim_next()["id"] == rows[0]["id"]
    assert second.claim_next() is None


@pytest.mark.parametrize("terminal", ["completed", "cancelled"])
def test_stale_dispatcher_cannot_rewind_retained_task(tmp_path, terminal):
    first, second = managers(tmp_path)
    created = first.create("approved", metadata())
    if terminal == "completed":
        first.claim_next()
        first.complete(created["id"], {"receipt": "retained"})
    else:
        first.cancel(created["id"])
    before = first.repo.get(created["id"])
    repeated = second.create("approved", metadata())
    assert repeated == before == first.repo.get(created["id"])
    assert second.claim_next() is None


def test_changed_operation_cannot_reuse_step_identity(tmp_path):
    first, second = managers(tmp_path)
    created = first.create("approved", metadata())
    before = first.repo.get(created["id"])
    with pytest.raises(ValueError, match="conflicts"):
        second.create("changed", metadata())
    with pytest.raises(ValueError, match="conflicts"):
        second.create("approved", {**metadata(), "tool_parameters": {"text": "changed"}})
    assert first.repo.get(created["id"]) == before


def test_insert_only_does_not_replace_existing_task(tmp_path):
    first, _ = managers(tmp_path)
    created = first.create("original")
    before = first.repo.get(created["id"])
    assert first.repo.save({**created, "prompt": "replacement"}, create_only=True) is False
    assert first.repo.get(created["id"]) == before
