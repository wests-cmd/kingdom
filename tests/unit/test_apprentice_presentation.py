from types import SimpleNamespace

import pytest

from backend.knights.presentation import knight_summary


class Nodes:
    def get_node(self, role):
        return {"active": False}


@pytest.mark.parametrize("role", ["planner", "coder", "researcher", "memory", "security"])
def test_public_apprentice_identity_keeps_legacy_routing_key(role):
    worker = SimpleNamespace(health="healthy", zero_trust=SimpleNamespace(nodes=Nodes()))
    result = knight_summary(role, worker, 0, 0)
    assert result["id"] == f"knight-{role}"
    assert result["public_id"] == f"Apprentices-{role}"
    assert result["display_name"] == f"Apprentices-{role}"
    assert result["entity_type"] == "apprentice"
    assert result["status"] == "offline"


def test_unknown_role_cannot_become_a_public_label():
    with pytest.raises(ValueError, match="Unknown"):
        knight_summary("<script>", None, 0, 0)
