"""A GitHub branch clean-up must preserve history and both keeper refs."""
from pathlib import Path
import importlib.util

PATH = Path(__file__).resolve().parents[1] / "scripts" / "retire_historical_branches.py"


def load():
    spec = importlib.util.spec_from_file_location("kingdom_retire", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retirement_list_is_pinned_and_excludes_keeper_branches():
    doc = load().load_manifest()
    assert doc["keepers"] == ["main", "integration/kingdom-cohesion-20261119"]
    assert len(doc["branches"]) == 35
    assert len(set(row["name"] for row in doc["branches"])) == 35
    assert all(len(row["sha"]) == 40 for row in doc["branches"])


def test_retirement_is_opt_in_and_refuses_missing_confirmation(monkeypatch):
    script = load()
    monkeypatch.setenv("RETIRE_MODE", "archive-and-delete")
    monkeypatch.setenv("GITHUB_REPOSITORY", "wests-cmd/kingdom")
    monkeypatch.delenv("RETIRE_CONFIRMATION", raising=False)
    try:
        script.main()
    except ValueError as exc:
        assert "confirmation" in str(exc).lower()
    else:
        raise AssertionError("Deletion unexpectedly allowed")

def test_every_branch_is_reviewed_and_unported_features_are_held():
    rows = load().load_manifest()["branches"]
    assert {row["disposition"] for row in rows} == {"integrated", "superseded", "review_required"}
    held = [row["name"] for row in rows if row["disposition"] == "review_required"]
    assert "codex/monitor-execution-guard-20261023" in held
    assert "jules-12217898583924398317-1da231a0" in held
    assert "feat/autonomous-harness-foundation-17802645864919866654" in held
    assert "jules-external-oracle-harness-4034832206850530088" in held


def test_review_required_branch_never_deleted_even_with_confirmation(monkeypatch):
    script = load()
    manifest = script.load_manifest()
    row = next(b for b in manifest["branches"] if b["disposition"] == "review_required")
    monkeypatch.setenv("RETIRE_MODE", "archive-and-delete")
    monkeypatch.setenv("RETIRE_CONFIRMATION", "ARCHIVE_AND_RETIRE_35")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "wests-cmd/kingdom")
    monkeypatch.setattr(script, "remote_heads",
                        lambda: {"main": "a" * 40, "integration/kingdom-cohesion-20261119": "b" * 40,
                                 row["name"]: row["sha"]})
    monkeypatch.setattr(script, "active_pull_request_heads", lambda repo: set())
    monkeypatch.setattr(script, "remote_tag_sha", lambda tag: row["sha"])
    commands = []
    monkeypatch.setattr(script, "run", lambda *args: commands.append(args) or "")
    script.main()
    assert commands == []


def test_archive_only_does_not_delete_even_with_open_pull_request(monkeypatch):
    script = load()
    manifest = script.load_manifest()
    row = next(b for b in manifest["branches"] if b["disposition"] == "integrated")
    monkeypatch.setenv("RETIRE_MODE", "archive-only")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "wests-cmd/kingdom")
    monkeypatch.delenv("RETIRE_CONFIRMATION", raising=False)
    monkeypatch.setattr(script, "remote_heads",
                        lambda: {"main": "a" * 40, "integration/kingdom-cohesion-20261119": "b" * 40,
                                 row["name"]: row["sha"]})
    monkeypatch.setattr(script, "active_pull_request_heads", lambda repo: {row["name"]})
    monkeypatch.setattr(script, "remote_tag_sha", lambda tag: row["sha"])
    commands = []
    monkeypatch.setattr(script, "run", lambda *args: commands.append(args) or "")
    script.main()
    assert commands == []
