"""Regression checks for public autonomy foundation access and claims."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_gap_register_requires_owner():
    source = (ROOT / "backend/system/gap_register_api.py").read_text()
    assert "Depends(require_owner)" in source
    assert "dependencies=[Depends(require_owner)]" in source

def test_unfinished_autonomy_not_advertised_as_verified():
    from backend.system.gap_register import INITIAL_CAPABILITIES
    by_id = {entry["id"]: entry for entry in INITIAL_CAPABILITIES}
    for name in ("autonomous-coding", "independent-verification", "automatic-releases", "beginner-installation", "recovery-after-restart", "security-isolation"):
        assert by_id[name]["status"] == "partial"
