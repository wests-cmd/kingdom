"""Maintain every explicitly approved peer link without granting membership."""
import asyncio


class PeerConnections:
    def __init__(self, registry, reconnect, events, interval=15):
        self.registry, self.reconnect, self.events = registry, reconnect, events
        self.interval = interval
        self.task = None
        self.status = {}
        self.limit = asyncio.Semaphore(4)

    async def tick(self):
        peers = {n.node_id: n for n in self.registry.list_nodes()
                 if not n.is_local and (n.public_identity or {}).get('node_type') == 'commander'
                 and n.node_state in {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}}
        self.status = {k: v for k, v in self.status.items() if k in peers}

        async def connect(node_id):
            async with self.limit:
                # Re-read after waiting: an owner may have revoked this peer.
                node = self.registry.get_node(node_id)
                if not node or node.node_state not in {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}:
                    self.status.pop(node_id, None)
                    return
                if not (node.connection_metadata or {}).get('kingdom_endpoint'):
                    state = 'endpoint_required'
                else:
                    try:
                        await asyncio.wait_for(self.reconnect(node_id), timeout=35)
                        state = 'verified'
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # Do not expose URLs, credentials or exception bodies.
                        state = 'retrying'
                if self.status.get(node_id) != state:
                    self.status[node_id] = state
                    self.events.publish('cluster.peer_connection', {'node_id': node_id, 'status': state})

        await asyncio.gather(*(connect(node_id) for node_id in peers))

    async def run(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A database/startup failure must not permanently stop recovery.
                pass
            await asyncio.sleep(self.interval)

    async def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())

    async def stop(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
