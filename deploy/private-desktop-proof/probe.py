"""Real private-X11 GUI event and screenshot check, executed offline in CI.

Evidence is limited to a disposable Debian container; it cannot certify
native Windows/macOS sessions or arbitrary application isolation.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from PIL import Image

EXPECTED = "kingdom-private-control-ok"
PROOF = Path("/tmp/private-desktop-confirmation.txt")
CAPTURE = Path("/tmp/private-desktop.png")


def command(*arguments):
    return subprocess.run(arguments, check=True, capture_output=True,
                          text=True, timeout=8).stdout.strip()


def prove_no_outbound_network():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.4)
        try:
            client.connect(("1.1.1.1", 443))
        except OSError:
            return
    raise RuntimeError("The disposable GUI worker unexpectedly has network egress")


def select_private_window():
    deadline = time.monotonic() + 9
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--name",
             "Kingdom Private Desktop Proof"],
            capture_output=True, text=True, timeout=3,
        )
        windows = [line.strip() for line in result.stdout.splitlines()
                   if line.strip().isdigit()]
        if windows:
            return windows[-1]
        time.sleep(0.15)
    raise RuntimeError("The native Tk app did not present a private X11 window")


def main():
    if os.geteuid() == 0 or os.environ.get("DISPLAY") != ":99":
        raise RuntimeError("Refusing root or any non-private display")
    prove_no_outbound_network()

    window = select_private_window()
    # X11 input travels only through DISPLAY=:99 inside the container.
    command("xdotool", "windowfocus", "--sync", window)
    command("xdotool", "type", "--clearmodifiers", "--delay", "8", EXPECTED)
    command("xdotool", "key", "Return")

    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and not PROOF.exists():
        time.sleep(0.12)
    if not PROOF.exists() or PROOF.read_text(encoding="utf-8") != EXPECTED:
        raise RuntimeError("The app did not receive and verify actual private-display input")

    command("xwd", "-root", "-silent", "-display", ":99",
            "-out", "/tmp/private-desktop.xwd")
    with Image.open("/tmp/private-desktop.xwd") as image:
        if image.size != (800, 600):
            raise RuntimeError("Private Xvfb screenshot dimensions do not match")
        image.convert("RGB").save(CAPTURE, format="PNG")

    data = CAPTURE.read_bytes()
    print(json.dumps({
        "result": "PASS", "display": ":99", "worker_uid": os.geteuid(),
        "network_egress": "blocked", "native_gui_input": "observed",
        "screenshot_dimensions": [800, 600],
        "screenshot_sha256": hashlib.sha256(data).hexdigest(),
        "scope": "Linux disposable Xvfb proof only; not public desktop certification",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
