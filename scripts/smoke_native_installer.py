"""Exercise the app extracted or installed from the actual release installer."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import hashlib
import socket
import time
import json
from validate_version import get_authoritative_version


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

platform = sys.argv[1]
root = Path.cwd()
version = get_authoritative_version(str(root))
env = dict(os.environ, KINGDOM_RELEASE_SMOKE_REPORT=str(root / "evidence" / "desktop.json"))
with tempfile.TemporaryDirectory(prefix="kingdom-install-") as temporary:
    destination = Path(temporary)
    mounted = False
    try:
        if platform == "windows":
            installer = root / f"desktop/dist/Kingdom-Setup-{version}.exe"
            subprocess.run([str(installer), "/S", f"/D={destination}"], check=True, timeout=120)
            app = destination / "Kingdom.exe"
            assert sha(destination / "resources/bin/kingdom-backend.exe") == sha(root / "desktop/bin/kingdom-backend.exe")
            subprocess.run([str(app)], env=env, check=True, timeout=120)
            # Reapply the real installer to the existing installation. User data
            # must survive without a manual uninstall or a repeated setup wizard.
            user_data = root / 'evidence/user-data'
            profile = user_data / 'local_profile.json'
            saved_profile = profile.read_bytes()
            database = user_data / 'runtime/data/kingdom.db'
            saved_database = sha(database)
            marker = user_data / 'runtime/data/update-retention-proof.txt'
            marker.write_text('retained owner data', encoding='utf-8')
            # Exercise the same real PowerShell handoff used by the native updater.
            # The helper waits for this short-lived Node process before installing.
            update_installer = root / 'evidence/verified-upgrade.exe'
            import shutil
            shutil.copy2(installer, update_installer)
            receipt = root / 'evidence/windows-upgrade.json'
            helper = """
const {handoffScript}=require('./desktop/updates');
const {spawn}=require('child_process');
const fs=require('fs');
const [installer,exe,digest,version,receipt]=process.argv.slice(1);
const script=handoffScript(process.pid,installer,exe,digest,version,receipt);
const child=spawn('powershell.exe',['-NoProfile','-NonInteractive','-EncodedCommand',Buffer.from(script,'utf16le').toString('base64')],{detached:true,windowsHide:true,stdio:['ignore',fs.openSync(receipt+'.log','a'),fs.openSync(receipt+'.log','a')]});
child.once('spawn',()=>{child.unref()});child.once('error',()=>process.exit(1));
"""
            subprocess.run(['node', '-e', helper, str(update_installer), str(app), sha(update_installer), version, str(receipt)], check=True, timeout=15)
            deadline = time.monotonic() + 150
            upgrade = None
            while time.monotonic() < deadline:
                try:
                    upgrade = json.loads(receipt.read_text(encoding='utf-8-sig'))
                    if upgrade.get('reopenedPID'):
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(1)
            assert upgrade and upgrade.get('success') is True and upgrade.get('reopenedPID'), f'Native upgrade handoff failed: {upgrade}'
            # This process belongs only to the isolated installer acceptance test.
            subprocess.run(['taskkill', '/PID', str(int(upgrade['reopenedPID'])), '/T', '/F'], check=True, timeout=15)
            assert not update_installer.exists(), 'Successful upgrade did not clean its download'
            assert profile.read_bytes() == saved_profile and marker.read_text() == 'retained owner data'
            assert sha(database) == saved_database, 'Windows upgrade changed the retained task database'
            assert sha(destination / 'resources/bin/kingdom-backend.exe') == sha(root / 'desktop/bin/kingdom-backend.exe')
            report_file = root / 'evidence/desktop.json'
            report = json.loads(report_file.read_text())
            report['desktopUpdates']['existingDataPreserved'] = True
            report_file.write_text(json.dumps(report, indent=2))
        elif platform == "macos":
            subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(destination),
                            str(root / f"desktop/dist/Kingdom-{version}.dmg")], check=True, timeout=120)
            mounted = True
            app = destination / "Kingdom.app/Contents/MacOS/Kingdom"
            assert sha(destination / "Kingdom.app/Contents/Resources/bin/kingdom-backend") == sha(root / "desktop/bin/kingdom-backend")
            subprocess.run([str(app)], env=env, check=True, timeout=120)
        elif platform == "linux":
            appimage = root / f"desktop/dist/Kingdom-{version}.AppImage"
            subprocess.run([str(appimage), "--appimage-extract"], cwd=destination, check=True, timeout=120,
                           stdout=subprocess.DEVNULL)
            app = destination / "squashfs-root/AppRun"
            subprocess.run(["xvfb-run", "-a", str(app), "--no-sandbox"], env=env, check=True, timeout=120)
            # Confirm the DEB contains the same tested application resources/backend.
            deb = root / f"desktop/dist/kingdom-desktop_{version}_amd64.deb"
            unpacked = destination / "deb"
            subprocess.run(["dpkg-deb", "-x", str(deb), str(unpacked)], check=True, timeout=120)
            assert sha(destination / "squashfs-root/resources/bin/kingdom-backend") == sha(root / "desktop/bin/kingdom-backend")
            for relative in ("resources/app.asar", "resources/bin/kingdom-backend"):
                assert sha(destination / "squashfs-root" / relative) == sha(unpacked / "opt/Kingdom" / relative)
        # A successful UI check must also leave no serving backend behind.
        with socket.socket() as connection:
            connection.settimeout(2)
            assert connection.connect_ex(("127.0.0.1", 8000)) != 0, "Orphaned backend after desktop shutdown"
    finally:
        if mounted:
            for attempt in range(3):
                detached = subprocess.run(["hdiutil", "detach", str(destination)], timeout=60)
                if detached.returncode == 0:
                    break
                time.sleep(2)
            detached.check_returncode()
