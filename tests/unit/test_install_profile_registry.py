"""
Unit & Doomsday Tests for Installation Profiles, Guided Setup, Hardware Detection, and Knight Selection.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from backend.knights.registry import KnightRegistry, load_enabled_knight_roles


def test_registry_default_no_profile(monkeypatch):
    monkeypatch.delenv("KINGDOM_LOCAL_PROFILE", raising=False)
    # Ensure non-existent profile file
    with tempfile.TemporaryDirectory() as tmpdir:
        non_existent = os.path.join(tmpdir, "missing.json")
        monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", non_existent)

        roles = load_enabled_knight_roles()
        assert set(roles) == {"planner", "coder", "researcher", "memory", "security"}

        registry = KnightRegistry()
        assert set(registry._knights.keys()) == {"planner", "coder", "researcher", "memory", "security"}


def test_registry_valid_profile(monkeypatch):
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        json.dump({"gui": True, "knights": ["planner", "coder", "security"]}, tmp)
        tmp_path = tmp.name

    try:
        monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", tmp_path)
        roles = load_enabled_knight_roles()
        assert roles == ["planner", "coder", "security"]

        registry = KnightRegistry()
        assert set(registry._knights.keys()) == {"planner", "coder", "security"}
        assert registry.get("coder") is not None
        assert registry.get("researcher") is None
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_registry_malformed_json_doomsday(monkeypatch):
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        tmp.write("{ invalid json content ...")
        tmp_path = tmp.name

    try:
        monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", tmp_path)
        roles = load_enabled_knight_roles()
        assert set(roles) == {"planner", "coder", "researcher", "memory", "security"}

        registry = KnightRegistry()
        assert set(registry._knights.keys()) == {"planner", "coder", "researcher", "memory", "security"}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_registry_unknown_knight_roles(monkeypatch):
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        json.dump({"gui": True, "knights": ["planner", "fake_knight", "not_real"]}, tmp)
        tmp_path = tmp.name

    try:
        monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", tmp_path)
        roles = load_enabled_knight_roles()
        assert roles == ["planner"]

        registry = KnightRegistry()
        assert list(registry._knights.keys()) == ["planner"]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_registry_empty_knight_list_fallback(monkeypatch):
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        json.dump({"gui": True, "knights": []}, tmp)
        tmp_path = tmp.name

    try:
        monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", tmp_path)
        roles = load_enabled_knight_roles()
        assert set(roles) == {"planner", "coder", "researcher", "memory", "security"}

        registry = KnightRegistry()
        assert set(registry._knights.keys()) == {"planner", "coder", "researcher", "memory", "security"}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_registry_duplicate_knight_roles(monkeypatch):
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        json.dump({"gui": True, "knights": ["planner", "coder", "planner", "coder", "memory"]}, tmp)
        tmp_path = tmp.name

    try:
        monkeypatch.setenv("KINGDOM_LOCAL_PROFILE", tmp_path)
        roles = load_enabled_knight_roles()
        assert roles == ["planner", "coder", "memory"]

        registry = KnightRegistry()
        assert list(registry._knights.keys()) == ["planner", "coder", "memory"]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_explicit_registry_construction():
    registry = KnightRegistry(enabled_roles=["memory"])
    assert list(registry._knights.keys()) == ["memory"]
    assert registry.get("memory") is not None
    assert registry.get("coder") is None


def test_explicit_registry_invalid_roles():
    registry = KnightRegistry(enabled_roles=["non_existent_knight"])
    # Fallback to all knights
    assert set(registry._knights.keys()) == {"planner", "coder", "researcher", "memory", "security"}


def test_install_profiles_catalog_file_integrity():
    catalog_path = Path(__file__).resolve().parents[2] / "configs" / "install_profiles.json"
    assert catalog_path.exists()

    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == 1
    assert "developer" in data["profiles"]
    assert "research" in data["profiles"]
    assert "full_swarm" in data["profiles"]
    assert "server_headless" in data["profiles"]
