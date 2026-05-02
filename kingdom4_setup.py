#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run(cmd):
    print(f"[RUN] {cmd}")
    subprocess.check_call(cmd, shell=True)

def ask(prompt, default=None):
    if default:
        text = input(f"{prompt} [{default}]: ").strip()
        return text or default
    return input(f"{prompt}: ").strip()

def main():
    print("=== Kingdom 4 Setup ===")
    role = ask("Is this machine a Commander, Knight, or Both? (c/k/b)", "c").lower()
    port = ask("Port for Commander web UI", "8000")

    venv_dir = ROOT / "venv"
    if not venv_dir.exists():
        run(f"python3 -m venv {venv_dir}")
    pip = venv_dir / "bin" / "pip"
    python = venv_dir / "bin" / "python"

    run(f"{pip} install --upgrade pip")
    run(f"{pip} install fastapi uvicorn psutil requests")

    print("\nSetup complete.\n")
    if role in ("c", "b"):
        print("Commander instructions:")
        print("  source venv/bin/activate")
        print(f"  uvicorn commander.commander:app --host 0.0.0.0 --port {port}")
    if role in ("k", "b"):
        print("\nKnight instructions:")
        print("  source venv/bin/activate")
        print("  python3 knight/knight_agent.py")

if __name__ == "__main__":
    main()
