"""Fail-closed independent checks for the disposable private X11 worker.

Uses only Python's standard library. These are container/fixture claims, not
a security certification of real desktop apps or production browsers.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def verify(directory):
    directory = Path(directory)
    host = json.loads((directory / "host-config.json").read_text(encoding="utf-8"))
    if host.get("NetworkMode") != "none":
        raise ValueError("Desktop worker network must be disconnected")
    if host.get("ReadonlyRootfs") is not True:
        raise ValueError("Desktop worker root filesystem must be read-only")
    if host.get("Privileged") is not False:
        raise ValueError("Privileged desktop worker refused")
    if "ALL" not in (host.get("CapDrop") or []):
        raise ValueError("Linux capabilities must all be dropped")
    if "no-new-privileges" not in (host.get("SecurityOpt") or []):
        raise ValueError("Worker must not be able to gain privilege")
    if host.get("Binds") or host.get("Mounts"):
        raise ValueError("The private demo must have no host bind or additional mount")
    if (host.get("PidsLimit") or 999) > 64:
        raise ValueError("Unbounded worker process count")
    if not 0 < (host.get("Memory") or 0) <= 512 * 1024 * 1024:
        raise ValueError("Worker has no bounded memory limit")
    if not 0 < (host.get("NanoCpus") or 0) <= 500_000_000:
        raise ValueError("Worker has no bounded CPU allocation")
    if "/tmp" not in (host.get("Tmpfs") or {}):
        raise ValueError("Offline worker needs an in-container private temporary filesystem")
    if host.get("PidMode") == "host" or host.get("IpcMode") == "host":
        raise ValueError("Worker must not share host process or IPC namespaces")

    accepted_input = (directory / "input-confirmation.txt").read_text(encoding="utf-8")
    if accepted_input != "kingdom-private-control-ok":
        raise ValueError("The native Tk fixture did not persist the required X11 input")
    lines = (directory / "worker-report.log").read_text(encoding="utf-8").splitlines()
    report = json.loads(next(line for line in reversed(lines) if line.strip()))
    if (report.get("result") != "PASS" or report.get("display") != ":99"
            or report.get("worker_uid") != 10001
            or report.get("network_egress") != "blocked"
            or report.get("native_gui_input") != "observed"
            or report.get("screenshot_dimensions") != [800, 600]):
        raise ValueError("Real private X11 input/display/network proof did not complete")
    screenshot = (directory / "private-desktop.png").read_bytes()
    if len(screenshot) < 100 or screenshot[:8] != PNG_MAGIC:
        raise ValueError("Worker did not retain a real PNG screenshot")
    if struct.unpack(">II", screenshot[16:24]) != (800, 600):
        raise ValueError("Screenshot image dimensions do not match private display")
    if hashlib.sha256(screenshot).hexdigest() != report.get("screenshot_sha256"):
        raise ValueError("Screenshot evidence changed after the real GUI test")
    print("Verified: restricted offline Linux Xvfb fixture; not OS-boundary product certification")


if __name__ == "__main__":
    verify(sys.argv[1] if len(sys.argv) == 2 else "evidence")
