"""Exercise the app extracted or installed from the actual release installer."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import hashlib


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

platform = sys.argv[1]
root = Path.cwd()
env = dict(os.environ, KINGDOM_RELEASE_SMOKE_REPORT=str(root / "evidence" / "desktop.json"))
with tempfile.TemporaryDirectory(prefix="kingdom-install-") as temporary:
    destination = Path(temporary)
    mounted = False
    try:
        if platform == "windows":
            installer = root / "desktop/dist/Kingdom-Setup-1.0.0.exe"
            subprocess.run([str(installer), "/S", f"/D={destination}"], check=True, timeout=120)
            app = destination / "Kingdom.exe"
            assert sha(destination / "resources/bin/kingdom-backend.exe") == sha(root / "desktop/bin/kingdom-backend.exe")
            subprocess.run([str(app)], env=env, check=True, timeout=120)
        elif platform == "macos":
            subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(destination),
                            str(root / "desktop/dist/Kingdom-1.0.0.dmg")], check=True, timeout=120)
            mounted = True
            app = destination / "Kingdom.app/Contents/MacOS/Kingdom"
            assert sha(destination / "Kingdom.app/Contents/Resources/bin/kingdom-backend") == sha(root / "desktop/bin/kingdom-backend")
            subprocess.run([str(app)], env=env, check=True, timeout=120)
        elif platform == "linux":
            appimage = root / "desktop/dist/Kingdom-1.0.0.AppImage"
            subprocess.run([str(appimage), "--appimage-extract"], cwd=destination, check=True, timeout=120,
                           stdout=subprocess.DEVNULL)
            app = destination / "squashfs-root/AppRun"
            subprocess.run(["xvfb-run", "-a", str(app), "--no-sandbox"], env=env, check=True, timeout=120)
            # Confirm the DEB contains the same tested application resources/backend.
            deb = root / "desktop/dist/kingdom-desktop_1.0.0_amd64.deb"
            unpacked = destination / "deb"
            subprocess.run(["dpkg-deb", "-x", str(deb), str(unpacked)], check=True, timeout=120)
            assert sha(destination / "squashfs-root/resources/bin/kingdom-backend") == sha(root / "desktop/bin/kingdom-backend")
            for relative in ("resources/app.asar", "resources/bin/kingdom-backend"):
                assert sha(destination / "squashfs-root" / relative) == sha(unpacked / "opt/Kingdom" / relative)
    finally:
        if mounted:
            subprocess.run(["hdiutil", "detach", str(destination)], check=True, timeout=60)
