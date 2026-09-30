"""Exercise the frozen process from an empty working directory without Python fallback."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

binary = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
with tempfile.TemporaryDirectory(prefix="kingdom-native-") as directory:
    env = dict(os.environ, KINGDOM_DATA_DIR=directory)
    log = Path(directory) / "backend.log"
    with log.open("wb") as output:
        process = subprocess.Popen([str(binary), "--port", str(port)], cwd=directory,
                                   env=env, stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(log.read_text(errors="replace"))
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=2) as response:
                        ready = json.load(response)
                    if ready.get("status") == "ready":
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError("Frozen backend readiness timed out: " + log.read_text(errors="replace"))
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/system/version") as response:
                version = json.load(response)
            assert version["version"] == "1.0.0", version
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
                html = response.read().decode()
            assert '<div id="root">' in html, html[:200]
            assert (Path(directory) / "data" / "kingdom.db").is_file()
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps({"platform": sys.platform, "backend_ready": ready,
                                         "version": version["version"], "frontend_served": True,
                                         "writable_user_data": True}, indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
