"""Unit-test the lab verifier itself; the separate Docker CI proves real X11 input."""
import hashlib
import json

from PIL import Image
import pytest

from scripts.verify_private_desktop_evidence import verify


@pytest.fixture
def evidence(tmp_path):
    config = {
        "NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
        "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"],
        "Binds": None, "Mounts": None, "PidsLimit": 64,
        "Memory": 512 * 1024 * 1024, "NanoCpus": 500_000_000,
        "Tmpfs": {"/tmp": "rw"}, "PidMode": "", "IpcMode": "private",
    }
    (tmp_path / "host-config.json").write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / "input-confirmation.txt").write_text("kingdom-private-control-ok", encoding="utf-8")
    capture = tmp_path / "private-desktop.png"
    Image.new("RGB", (800, 600)).save(capture, "PNG")
    report = {
        "result": "PASS", "display": ":99", "worker_uid": 10001,
        "network_egress": "blocked", "native_gui_input": "observed",
        "screenshot_dimensions": [800, 600],
        "screenshot_sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
    }
    (tmp_path / "worker-report.log").write_text(json.dumps(report) + "\n", encoding="utf-8")
    return tmp_path


def test_evidence_verifier_accepts_a_consistent_report_but_does_not_prove_real_gui(evidence):
    verify(evidence)


@pytest.mark.parametrize("key,value", [
    ("NetworkMode", "bridge"),
    ("ReadonlyRootfs", False),
    ("Privileged", True),
    ("CapDrop", []),
    ("SecurityOpt", []),
    ("Binds", ["/home/user:/home/user"]),
    ("Mounts", [{"Type": "bind"}]),
    ("PidsLimit", 1000),
    ("Memory", 0),
    ("NanoCpus", 2_000_000_000),
    ("Tmpfs", {}),
    ("PidMode", "host"),
    ("IpcMode", "host"),
])
def test_verifier_denies_weak_worker_config(evidence, key, value):
    path = evidence / "host-config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config[key] = value
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError):
        verify(evidence)


def test_verifier_denies_tampered_image(evidence):
    target = evidence / "private-desktop.png"
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Screenshot evidence changed"):
        verify(evidence)


def test_verifier_denies_invented_native_input(evidence):
    target = evidence / "worker-report.log"
    report = json.loads(target.read_text(encoding="utf-8"))
    report["native_gui_input"] = "simulated"
    target.write_text(json.dumps(report) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Real private X11"):
        verify(evidence)



def test_verifier_denies_missing_native_ui_confirmation(evidence):
    (evidence / "input-confirmation.txt").write_text("model-says-done", encoding="utf-8")
    with pytest.raises(ValueError, match="did not persist"):
        verify(evidence)
