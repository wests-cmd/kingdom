"""Maintain every explicitly approved peer link without granting membership."""
import asyncio
import time


class PeerConnections:
    def __init__(self, registry, reconnect, events, interval=15, refresh=None, work=None, clock=time.monotonic):
        self.registry, self.reconnect, self.events = registry, reconnect, events
        self.interval = interval
        self.task = None
        self.status = {}
        self.limit = asyncio.Semaphore(4)
        self.refresh = refresh
        self.work = work
        self.clock = clock
        self.connections = {}
        self.work_tasks = {}
        self.work_limit = asyncio.Semaphore(2)
        self.refresh_task = None
        self.retry = {}

    async def _refresh(self):
        try:
            await asyncio.wait_for(self.refresh(), timeout=35)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass  # An unavailable authority must not prevent existing links.

    async def _work(self, node_id, pinned, address):
        async with self.work_limit:
            try:
                node = self.registry.get_node(node_id)
                if (not node or node.node_state != 'CONNECTED' or node.public_identity != pinned
                        or (node.connection_metadata or {}).get('kingdom_endpoint') != address):
                    return
                deadline = (node.connection_metadata or {}).get('membership_expires_at')
                if deadline is not None and deadline <= time.time():
                    return
                await asyncio.wait_for(self.work(node_id), timeout=20)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.events.publish('cluster.native_analysis_held', {'controller_id': node_id})

    async def tick(self, wait=True):
        if self.refresh and (self.refresh_task is None or self.refresh_task.done()):
            self.refresh_task = asyncio.create_task(self._refresh())
        peers = {n.node_id: n for n in self.registry.list_nodes()
                 if not n.is_local and (n.public_identity or {}).get('node_type') == 'commander'
                 and n.node_state in {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}}
        self.status = {k: v for k, v in self.status.items() if k in peers}
        self.retry = {k: v for k, v in self.retry.items() if k in peers}
        for tasks in (self.connections, self.work_tasks):
            for ident, task in list(tasks.items()):
                if task.done():
                    del tasks[ident]
                    if not task.cancelled():
                        task.result()  # Retrieve failures rather than silently leaking them.
                elif ident not in peers:
                    task.cancel()

        async def connect(node_id):
            async with self.limit:
                # Re-read after waiting: an owner may have revoked this peer.
                node = self.registry.get_node(node_id)
                if not node or node.node_state not in {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}:
                    self.status.pop(node_id, None)
                    return
                deadline = (node.connection_metadata or {}).get('membership_expires_at')
                if deadline is not None and deadline <= time.time():
                    self.status[node_id] = 'membership_expired'
                    return
                if not (node.connection_metadata or {}).get('kingdom_endpoint'):
                    state = 'endpoint_required'
                else:
                    try:
                        pinned = dict(node.public_identity or {})
                        address = node.connection_metadata['kingdom_endpoint']
                        await asyncio.wait_for(self.reconnect(node_id), timeout=35)
                        current = self.registry.get_node(node_id)
                        if (not current or current.node_state not in {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}
                                or current.public_identity != pinned
                                or (current.connection_metadata or {}).get('kingdom_endpoint') != address):
                            self.status.pop(node_id, None)
                            return
                        deadline = (current.connection_metadata or {}).get('membership_expires_at')
                        if deadline is not None and deadline <= time.time():
                            self.status[node_id] = 'membership_expired'
                            return
                        state = 'verified'
                        self.retry.pop(node_id, None)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # Do not expose URLs, credentials or exception bodies.
                        state = 'retrying'
                        failures = min(self.retry.get(node_id, (0, 0))[0] + 1, 4)
                        self.retry[node_id] = (failures, self.clock() + min(self.interval * 2 ** (failures - 1), 120))
                if self.status.get(node_id) != state:
                    self.status[node_id] = state
                    self.events.publish('cluster.peer_connection', {'node_id': node_id, 'status': state})
                if state=='verified' and self.work:
                    task = self.work_tasks.get(node_id)
                    if task is None or task.done():
                        self.work_tasks[node_id] = asyncio.create_task(self._work(node_id, pinned, address))

        launched = []
        for node_id in peers:
            if node_id in self.connections or self.retry.get(node_id, (0, 0))[1] > self.clock():
                continue
            task = asyncio.create_task(connect(node_id))
            self.connections[node_id] = task
            launched.append(task)
        if wait:
            await asyncio.gather(*launched)

    async def run(self):
        while True:
            try:
                await self.tick(wait=False)
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
        tasks = [*self.connections.values(), *self.work_tasks.values()]
        if self.refresh_task is not None:
            tasks.append(self.refresh_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.connections.clear()
        self.work_tasks.clear()
        self.refresh_task = None
