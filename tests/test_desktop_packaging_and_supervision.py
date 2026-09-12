"""
Tests for Desktop Application Packaging, Electron Builder Configuration, and Process Supervision.
"""

import pytest
import json
import os
from pathlib import Path


def test_desktop_package_json_manifest():
    desktop_pkg = Path(__file__).resolve().parents[1] / "desktop" / "package.json"
    assert desktop_pkg.exists()

    data = json.loads(desktop_pkg.read_text())
    assert data["name"] == "kingdom-desktop"
    assert data["version"] == "40.2.0"
    assert "electron" in data["dependencies"]
    assert "build" in data
    assert "win" in data["build"]
    assert "mac" in data["build"]
    assert "linux" in data["build"]


def test_desktop_main_security_preferences():
    desktop_main = Path(__file__).resolve().parents[1] / "desktop" / "main.js"
    assert desktop_main.exists()

    content = desktop_main.read_text()
    assert "nodeIntegration: false" in content
    assert "contextIsolation: true" in content


def test_desktop_doctor_diagnostics():
    desktop_doctor = Path(__file__).resolve().parents[1] / "desktop" / "doctor.js"
    assert desktop_doctor.exists()

    content = desktop_doctor.read_text()
    assert "runDoctorDiagnostics" in content
