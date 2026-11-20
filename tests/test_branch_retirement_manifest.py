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


def setup_one_branch(monkeypatch, *, disposition="integrated", is_open=False, moved=False, tag_exists=True):
    script = load()
    row = next(b for b in script.load_manifest()["branches"]
               if b["disposition"] == disposition)
    monkeypatch.setenv("RETIRE_MODE", "archive-and-delete")
    monkeypatch.setenv("RETIRE_CONFIRMATION", "ARCHIVE_AND_RETIRE_35")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "wests-cmd/kingdom")
    monkeypatch.setattr(script, "remote_heads", lambda: {
        "main": "a" * 40, "integration/kingdom-cohesion-20261119": "b" * 40,
        row["name"]: ("c" * 40 if moved else row["sha"])
    })
    monkeypatch.setattr(script, "active_pull_request_heads",
                        lambda repository: {row["name"]} if is_open else set())
    archived = [tag_exists]
    monkeypatch.setattr(script, "remote_tag_sha",
                        lambda tag: row["sha"] if archived[0] else None)
    commands = []
    def fake_run(*args):
        commands.append(args)
        if args[:3] == ("git", "push", "origin"):
            archived[0] = True
        return ""
    monkeypatch.setattr(script, "run", fake_run)
    return script, row, commands


def test_historical_ref_requires_no_open_pr(monkeypatch):
    script, row, commands = setup_one_branch(monkeypatch, is_open=True)
    script.main()
    assert commands == []


def test_moved_sha_is_not_archived_or_deleted(monkeypatch):
    script, row, commands = setup_one_branch(monkeypatch, moved=True)
    script.main()
    assert commands == []


def test_verified_safe_ref_retired_with_expected_sha_lease(monkeypatch):
    script, row, commands = setup_one_branch(monkeypatch)
    script.main()
    assert commands == [("git", "push", "--force-with-lease=refs/heads/" + row["name"] + ":" + row["sha"],
                         "origin", ":refs/heads/" + row["name"])]


def test_archive_tag_must_exist_before_retiring(monkeypatch):
    script, row, commands = setup_one_branch(monkeypatch, tag_exists=False)
    script.main()
    tag = "kingdom-history/2026-11-19/" + row["name"]
    assert commands == [("git", "tag", tag, row["sha"]),
                        ("git", "push", "origin", "refs/tags/" + tag),
                        ("git", "push", "--force-with-lease=refs/heads/" + row["name"] + ":" + row["sha"],
                         "origin", ":refs/heads/" + row["name"])]
