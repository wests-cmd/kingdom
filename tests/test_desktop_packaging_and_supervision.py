"""
Tests for Desktop Application Packaging, Electron Builder Configuration, Hardware Detection, Guided Setup, and Process Supervision.
"""

import pytest
import json
import os
import subprocess
from pathlib import Path


def test_desktop_package_json_manifest():
    desktop_pkg = Path(__file__).resolve().parents[1] / "desktop" / "package.json"
    assert desktop_pkg.exists()

    data = json.loads(desktop_pkg.read_text())
    assert data["name"] == "kingdom-desktop"
    assert data["version"] == "1.1.0"
    assert "electron" in data["devDependencies"]
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
    assert "validateProfile" in content
    assert "loadInstallCatalog" in content
    assert "loadSavedProfile" in content


def test_desktop_preload_bridge():
    preload_path = Path(__file__).resolve().parents[1] / "desktop" / "preload.js"
    assert preload_path.exists()

    content = preload_path.read_text()
    assert "getHardwareReport" in content
    assert "getInstallCatalog" in content
    assert "saveProfile" in content


def test_desktop_setup_wizard_exists():
    wizard_path = Path(__file__).resolve().parents[1] / "desktop" / "setup-wizard.html"
    assert wizard_path.exists()

    content = wizard_path.read_text()
    assert "Set Up Kingdom" in content
    assert "kingdomDesktop" in content


def test_desktop_hardware_detection_execution():
    hardware_js = Path(__file__).resolve().parents[1] / "desktop" / "hardware.js"
    assert hardware_js.exists()

    test_script = """
    const assert = require('assert');
    const { getHardwareReport, suggestProfile } = require('./desktop/hardware');

    const report = getHardwareReport();
    assert.strictEqual(typeof report.platform, 'string');
    assert.strictEqual(typeof report.arch, 'string');
    assert.strictEqual(typeof report.cpu_cores, 'number');
    assert.strictEqual(typeof report.memory_total_gb, 'number');
    assert.strictEqual(typeof report.gpu, 'object');

    assert.strictEqual(suggestProfile({ ...report, has_display: false }), 'server_headless');
    assert.strictEqual(suggestProfile({ ...report, has_display: true, memory_total_gb: 2.0, cpu_cores: 4 }), 'server_headless');
    assert.strictEqual(suggestProfile({ ...report, has_display: true, memory_total_gb: 16.0, cpu_cores: 8 }), 'full_swarm');
    assert.strictEqual(suggestProfile({ ...report, has_display: true, memory_total_gb: 4.0, cpu_cores: 2 }), 'developer');
    """

    res = subprocess.run(["node", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node hardware check failed: {res.stderr}"


def test_desktop_doctor_diagnostics():
    desktop_doctor = Path(__file__).resolve().parents[1] / "desktop" / "doctor.js"
    assert desktop_doctor.exists()

    content = desktop_doctor.read_text()
    assert "runDoctorDiagnostics" in content
