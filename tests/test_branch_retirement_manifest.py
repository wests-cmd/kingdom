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
