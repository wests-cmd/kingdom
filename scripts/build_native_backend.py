"""Build on the target OS; never ship a Linux backend inside another OS installer."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
bin_dir = root / "desktop" / "bin"
bin_dir.mkdir(exist_ok=True)
# An ignored development binary can be present in a checkout. Stage only this build.
for name in ("kingdom-backend", "kingdom-backend.exe"):
    candidate = bin_dir / name
    if candidate.exists():
        candidate.unlink()
subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
    "--name", "kingdom-backend", "--distpath", str(bin_dir), "--paths", str(root),
    "--collect-submodules", "uvicorn", "--collect-submodules", "backend",
    "--add-data", f"{root / 'frontend' / 'dist'}:frontend/dist",
    "--add-data", f"{root / 'migrations'}:migrations",
    "--add-data", f"{root / 'configs' / 'install_profiles.json'}:configs",
    str(root / "scripts" / "desktop_backend.py"),
], cwd=root, check=True)
