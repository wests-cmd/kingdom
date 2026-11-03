import asyncio
import threading
from types import SimpleNamespace

from backend.cluster.node_registry import NodeRegistry
from backend.cluster.peer_connections import PeerConnections
from backend.storage.db import Database
from backend.storage.repository import KnightRepository


def test_busy_registry_does_not_block_http_loop(tmp_path):
    database = Database(tmp_path / 'peers.db')
    registry = NodeRegistry(repository=KnightRepository(database))
    locked, release = threading.Event(), threading.Event()

    def writer():
        with database.get_connection() as conn:
            conn.execute('BEGIN EXCLUSIVE')
            locked.set()
            release.wait(2)

    thread = threading.Thread(target=writer)
    thread.start()
    assert locked.wait(2)

    async def observe():
        runner = PeerConnections(registry, None, SimpleNamespace(publish=lambda *args: None))
        pending = asyncio.create_task(runner.tick())
        # A scheduled HTTP response must run while the peer read is still locked.
        # The writer's bounded wait lets the broken implementation finish too.
        await asyncio.sleep(.05)
        responsive = not release.is_set() and not pending.done()
        release.set()
        await pending
        return responsive

    try:
        assert asyncio.run(observe()), 'SQLite peer lookup blocked the HTTP event loop'
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive()
