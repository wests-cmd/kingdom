import json
import os
import tempfile
import pytest
from backend.knights.registry import KnightRegistry, load_enabled_knight_roles, ALL_KNOWN_ROLES


def test_no_profile_enables_all_knights(monkeypatch):
    monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", "/nonexistent/profile_path.json")
    roles = load_enabled_knight_roles()
    assert sorted(roles) == sorted(ALL_KNOWN_ROLES)

    registry = KnightRegistry()
    assert sorted(registry._knights.keys()) == sorted(ALL_KNOWN_ROLES)


def test_valid_profile_restricts_active_knights(monkeypatch, tmp_path):
    prof_file = tmp_path / "local_profile.json"
    prof_file.write_text(json.dumps({
        "name": "Developer",
        "gui": True,
        "knights": ["coder", "planner"]
    }))
    monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", str(prof_file))

    roles = load_enabled_knight_roles()
    assert roles == ["coder", "planner"]

    registry = KnightRegistry()
    assert sorted(registry._knights.keys()) == ["coder", "planner"]


def test_malformed_json_falls_back_to_all_knights(monkeypatch, tmp_path):
    prof_file = tmp_path / "local_profile.json"
    prof_file.write_text("INVALID_JSON_CONTENT{{{")
    monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", str(prof_file))

    roles = load_enabled_knight_roles()
    assert sorted(roles) == sorted(ALL_KNOWN_ROLES)


def test_profile_ignores_unknown_knight_names(monkeypatch, tmp_path):
    prof_file = tmp_path / "local_profile.json"
    prof_file.write_text(json.dumps({
        "knights": ["coder", "does_not_exist", "planner"]
    }))
    monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", str(prof_file))

    roles = load_enabled_knight_roles()
    assert roles == ["coder", "planner"]


def test_profile_with_no_valid_knights_falls_back_to_all(monkeypatch, tmp_path):
    prof_file = tmp_path / "local_profile.json"
    prof_file.write_text(json.dumps({
        "knights": ["invalid_1", "invalid_2"]
    }))
    monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", str(prof_file))

    roles = load_enabled_knight_roles()
    assert sorted(roles) == sorted(ALL_KNOWN_ROLES)


def test_explicit_enabled_roles_override():
    registry = KnightRegistry(enabled_roles=["memory"])
    assert list(registry._knights.keys()) == ["memory"]


def test_duplicate_knight_names_deduplicated(monkeypatch, tmp_path):
    prof_file = tmp_path / "local_profile.json"
    prof_file.write_text(json.dumps({
        "knights": ["coder", "coder", "planner", "planner", "coder"]
    }))
    monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", str(prof_file))

    roles = load_enabled_knight_roles()
    assert roles == ["coder", "planner"]

    registry = KnightRegistry()
    assert list(registry._knights.keys()) == ["coder", "planner"]


def test_missing_profile_path_does_not_crash(monkeypatch):
    monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", "/path/that/definitely/does/not/exist.json")
    registry = KnightRegistry()
    assert sorted(registry._knights.keys()) == sorted(ALL_KNOWN_ROLES)


def test_kingdom_local_profile_env_var_override(monkeypatch, tmp_path):
    prof_file = tmp_path / "custom_env_profile.json"
    prof_file.write_text(json.dumps({
        "knights": ["researcher", "memory"]
    }))
    monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", str(prof_file))

    registry = KnightRegistry()
    assert sorted(registry._knights.keys()) == ["memory", "researcher"]
