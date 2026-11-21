import asyncio
from types import SimpleNamespace

from backend.cluster.node_registry import NodeRegistry
from backend.cluster.peer_connections import PeerConnections
from backend.storage.db import Database
from backend.storage.repository import KnightRepository


def test_busy_registry_does_not_block_http_loop(tmp_path):
    database = Database(tmp_path / 'peers.db')
    registry = NodeRegistry(repository=KnightRepository(database))
    from threading import Event
    locked, release = Event(), Event()

    # With SQLite WAL, an EXCLUSIVE writer no longer blocks reader snapshots.
    # Block the actual registry operation instead so this tests the event-loop
    # offload contract independently of the storage journal implementation.
    real_list = registry.list_nodes

    def slow_registry():
        locked.set()
        release.wait(2)
        return real_list()

    registry.list_nodes = slow_registry

    async def observe():
        runner = PeerConnections(registry, None, SimpleNamespace(publish=lambda *args: None))
        pending = asyncio.create_task(runner.tick())
        # A scheduled HTTP response must run while the peer read is still locked.
        # The writer's bounded wait lets the broken implementation finish too.
        # Verify the registry call actually reached the deliberate barrier.
        for _ in range(200):
            if locked.is_set():
                break
            await asyncio.sleep(.005)
        assert locked.is_set(), 'Registry did not reach test barrier'
        responsive = not release.is_set() and not pending.done()
        release.set()
        await pending
        return responsive

    try:
        assert asyncio.run(observe()), 'Slow peer registry blocked the HTTP event loop'
    finally:
        release.set()
