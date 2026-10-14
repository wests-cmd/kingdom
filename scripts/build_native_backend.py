"""Build on the target OS; never ship a Linux backend inside another OS installer."""
from pathlib import Path
import shutil
import subprocess
import sys
import os

root = Path(__file__).resolve().parents[1]
bin_dir = root / "desktop" / "bin"
bin_dir.mkdir(exist_ok=True)
# An ignored development binary can be present in a checkout. Stage only this build.
for name in ("kingdom-backend", "kingdom-backend.exe"):
    candidate = bin_dir / name
    if candidate.exists():
        candidate.unlink()
signed_directory = os.getenv('KINGDOM_BACKEND_LAYOUT') == 'onedir'
if signed_directory and sys.platform != 'win32':
    raise ValueError('The signable directory layout is Windows-only')
dist_dir = root/'build'/'signable-backend' if signed_directory else bin_dir
subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir" if signed_directory else "--onefile",
    "--name", "kingdom-backend", "--distpath", str(dist_dir), "--paths", str(root),
    "--collect-submodules", "uvicorn", "--collect-submodules", "backend",
    "--add-data", f"{root / 'frontend' / 'dist'}:frontend/dist",
    "--add-data", f"{root / 'migrations'}:migrations",
    "--add-data", f"{root / 'configs' / 'install_profiles.json'}:configs",
    str(root / "scripts" / "desktop_backend.py"),
], cwd=root, check=True)
if signed_directory:
    # Keep backend.exe at the existing launcher path while exposing every DLL
    # and extension for signing before they enter the desktop installer.
    shutil.copytree(dist_dir/'kingdom-backend', bin_dir, dirs_exist_ok=True)
