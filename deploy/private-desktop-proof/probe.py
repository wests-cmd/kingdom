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
TARGET = Path("/tmp/private-desktop-target.json")
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


def target_coordinates():
    deadline = time.monotonic() + 9
    while time.monotonic() < deadline:
        if TARGET.exists():
            value = json.loads(TARGET.read_text(encoding="utf-8"))
            x, y = value.get("x"), value.get("y")
            if type(x) is int and type(y) is int and 0 <= x < 800 and 0 <= y < 600:
                return str(x), str(y)
            raise RuntimeError("The private Tk input target is outside the Xvfb display")
        time.sleep(0.1)
    raise RuntimeError("The native Tk entry was never mapped to the private display")


def main():
    if os.geteuid() == 0 or os.environ.get("DISPLAY") != ":99":
        raise RuntimeError("Refusing root or any non-private display")
    prove_no_outbound_network()

    select_private_window()
    x, y = target_coordinates()
    # The test issues genuine XTEST mouse and keyboard events. The X server
    # and Tk fixture both live in the restricted container, not on the host.
    command("xdotool", "mousemove", "--sync", x, y)
    command("xdotool", "click", "1")
    command("xdotool", "type", "--clearmodifiers", "--delay", "8", EXPECTED)
    command("xdotool", "key", "Return")

    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and not PROOF.exists():
        time.sleep(0.12)
    try:
        if not PROOF.exists() or PROOF.read_text(encoding="utf-8") != EXPECTED:
            raise RuntimeError("The app did not receive and verify actual private-display input")
    finally:
        # Capture the private desktop on either success or a failed GUI event.
        # A red test still retains visual evidence, never host screenshots.
        command("xwd", "-root", "-silent", "-display", ":99",
                "-out", "/tmp/private-desktop.xwd")
        # Debian's Pillow cannot necessarily decode XWD directly. Convert
        # the real X11 capture to PNM with netpbm before reading pixels.
        with open("/tmp/private-desktop.xwd", "rb") as raw_xwd:
            with open("/tmp/private-desktop.ppm", "wb") as converted:
                subprocess.run(["xwdtopnm"], stdin=raw_xwd, stdout=converted,
                               check=True, timeout=8)
        with Image.open("/tmp/private-desktop.ppm") as image:
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
