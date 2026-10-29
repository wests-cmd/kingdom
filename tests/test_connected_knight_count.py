"""Home counts observed connections, not retained pairing membership."""
import sys
from types import SimpleNamespace

import pytest

from backend.cluster.apprentice_inventory import aggregate_inventories
from backend.runtime.orchestration_api import overview
from backend.storage.db import Database


def peer(ident, state='DISCONNECTED', received=None, heartbeat=1000):
    metadata = {} if received is None else {'apprentice_inventory': {
        'received_at': received, 'report': {'version': 1, 'apprentices': []}}}
    return {'node_id': ident, 'node_state': state, 'last_heartbeat': heartbeat,
            'connection_metadata': metadata}


@pytest.mark.parametrize('peers,connected', [
    ([peer(str(i)) for i in range(3)], 0),
    ([peer('live', 'CONNECTED', 1000), peer('off'), peer('stale', 'CONNECTED', 900)], 1),
    ([peer('membership-only', 'CONNECTED'), peer('old-heartbeat', 'CONNECTED', 1000, 900)], 0),
    ([peer('future', 'CONNECTED', 1001), peer('revoked', 'REVOKED', 1000)], 0),
])
def test_home_counts_only_current_authenticated_peer_reports(tmp_path, monkeypatch, peers, connected):
    import backend.storage.db as storage
    import backend.cluster.hierarchy as hierarchy
    import backend.runtime.orchestration_api as api
    database = Database(tmp_path / 'state.db')
    with database.get_connection() as conn:
        conn.execute('CREATE TABLE conversation_requests(state_json TEXT)'); conn.commit()
    monkeypatch.setattr(storage, 'db', database)
    monkeypatch.setattr(api.time, 'time', lambda: 1000)
    inventory = aggregate_inventories([], peers, now=1000)
    exported = {'knights': peers, 'commander': {}, 'apprentices': [], 'inventory': inventory}
    monkeypatch.setattr(hierarchy, 'CommandHierarchy', lambda *args: SimpleNamespace(export=lambda _: exported))
    monkeypatch.setitem(sys.modules, 'backend.api', SimpleNamespace(
        engine=SimpleNamespace(events=SimpleNamespace(publish=lambda *args: None), tasks=SimpleNamespace(list=lambda: [])),
        knights=lambda: {'knights': []}))
    monkeypatch.setitem(sys.modules, 'backend.runtime.agent_api', SimpleNamespace(service=lambda: None))
    monkeypatch.setitem(sys.modules, 'backend.runtime.request_api', SimpleNamespace(
        background=SimpleNamespace(active={}, status=lambda: {}), service=lambda: None))
    result = overview()
    assert result['counts']['knights'] == 1 + connected
    assert result['counts']['connected_peers'] == connected
    assert result['counts']['paired_knights'] == len(peers)
    assert result['counts']['unavailable_peers'] == len(peers) - connected
    assert result['knights'] == peers  # Offline nodes remain visible; no trust or membership changes.
    assert result['inventory']['total_current'] == 0
