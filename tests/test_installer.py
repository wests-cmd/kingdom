import pytest
import os
import subprocess
import sys

def test_python_setup_script():
    setup_script = "scripts/kingdom_setup.py"
    assert os.path.exists(setup_script)

    res = subprocess.run([sys.executable, setup_script, "--non-interactive"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "KINGDOM UNIVERSAL RUNTIME INSTALLER v40.1" in res.stdout
    assert "SUCCESS: Kingdom v40.1 installed successfully." in res.stdout

def test_install_sh_exists():
    assert os.path.exists("scripts/install.sh")
