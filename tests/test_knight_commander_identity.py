"""Commander identity must be looked up, never guessed when a remote node fails."""
import pytest
from backend.cluster.knight_daemon import KnightDaemon


def daemon_for_test(answer):
    daemon = object.__new__(KnightDaemon)
    daemon.node_id = "test-worker"
    daemon._http_request = lambda method, path, payload=None: answer
    return daemon


@pytest.mark.parametrize("answer", [{}, {"node_id": None}, {"node_id": ""},
                                    {"node_id": "with whitespace"}, {"node_id": 42}])
def test_missing_or_invalid_commander_identity_refused(answer):
    daemon = daemon_for_test(answer)
    with pytest.raises(RuntimeError):
        daemon._get_commander_id()


def test_lookup_network_failure_does_not_fall_back_to_default():
    daemon = daemon_for_test({})
    def unreachable(*_args, **_kwargs):
        raise RuntimeError("Commander unreachable")
    daemon._http_request = unreachable
    with pytest.raises(RuntimeError, match="unreachable"):
        daemon._get_commander_id()


def test_valid_commander_identity_is_preserved():
    assert daemon_for_test({"node_id": "KG-MASTER-01"})._get_commander_id() == "KG-MASTER-01"
