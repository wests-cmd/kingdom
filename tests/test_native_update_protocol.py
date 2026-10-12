import subprocess
from pathlib import Path

def test_native_update_protocol():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', '--test', 'desktop/updates.test.js'], cwd=root, check=True)
