import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('peer_connections', Path(__file__).parents[1] / 'backend/cluster/peer_connections.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def peer(ident, state='APPROVED', endpoint=True):
    return SimpleNamespace(node_id=ident, node_state=state, is_local=False,
                           public_identity={'node_type': 'commander'},
                           connection_metadata={'kingdom_endpoint': 'https://peer'} if endpoint else {},
                           granted_capabilities=[])


class ConnectionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_unavailable_authority_does_not_delay_existing_peer_heartbeat(self):
        blocked, connected = asyncio.Event(), asyncio.Event()
        async def refresh(): await blocked.wait()
        async def reconnect(ident): connected.set()
        node = peer('one')
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: [node], get_node=lambda _: node),
            reconnect, SimpleNamespace(publish=lambda *args: None), refresh=refresh)
        await runner.start()
        try:
            await asyncio.wait_for(connected.wait(), timeout=1)
        finally:
            await runner.stop()

    async def test_slow_peer_does_not_delay_healthy_peer_next_cycle(self):
        blocked, repeated = asyncio.Event(), asyncio.Event()
        calls = []
        nodes = {'slow': peer('slow'), 'healthy': peer('healthy')}
        async def reconnect(ident):
            calls.append(ident)
            if ident == 'slow': await blocked.wait()
            elif calls.count('healthy') >= 3: repeated.set()
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: list(nodes.values()), get_node=nodes.get),
            reconnect, SimpleNamespace(publish=lambda *args: None), interval=.01)
        await runner.start()
        try:
            await asyncio.wait_for(repeated.wait(), timeout=1)
            self.assertEqual(calls.count('slow'), 1)
        finally:
            await runner.stop()

    async def test_new_approved_peer_is_seen_without_restart_and_revocation_stops_it(self):
        nodes = {'one': peer('one')}
        calls, events = [], []
        async def reconnect(ident): calls.append(ident)
        registry = SimpleNamespace(list_nodes=lambda: list(nodes.values()), get_node=nodes.get)
        runner = module.PeerConnections(registry, reconnect, SimpleNamespace(publish=lambda *args: events.append(args)))
        await runner.tick()
        nodes['two'] = peer('two')
        await runner.tick()
        self.assertEqual(calls, ['one', 'one', 'two'])
        nodes['one'].node_state = 'REVOKED'
        await runner.tick()
        self.assertEqual(calls[-1], 'two')
        self.assertNotIn('one', runner.status)
        self.assertEqual(nodes['two'].granted_capabilities, [])
        self.assertEqual(len(events), 2)  # unchanged healthy links do not spam

    async def test_unapproved_and_missing_endpoints_never_connect(self):
        nodes = {s: peer(s, s) for s in ['REVOKED', 'REJECTED', 'QUARANTINED', 'PENDING_APPROVAL']}
        nodes['missing'] = peer('missing', endpoint=False)
        async def reconnect(ident): self.fail('Unapproved/missing endpoint attempted')
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: list(nodes.values()), get_node=nodes.get), reconnect,
                                        SimpleNamespace(publish=lambda *args: None))
        await runner.tick()
        self.assertEqual(runner.status, {'missing': 'endpoint_required'})

    async def test_failure_is_retried_and_start_stop_is_idempotent(self):
        node = peer('one')
        calls = []
        now = [0]
        async def reconnect(ident):
            calls.append(ident)
            if len(calls) == 1: raise OSError('offline')
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: [node], get_node=lambda _: node), reconnect,
                                        SimpleNamespace(publish=lambda *args: None), clock=lambda: now[0])
        await runner.tick()
        self.assertEqual(runner.status['one'], 'retrying')
        await runner.tick()
        self.assertEqual(len(calls), 1)
        now[0] = 15
        await runner.tick()
        self.assertEqual(runner.status['one'], 'verified')
        await runner.start()
        task = runner.task
        await runner.start()
        self.assertIs(runner.task, task)
        await runner.stop()
        self.assertTrue(task.done())
        self.assertIsNone(runner.task)

    async def test_slow_analysis_cannot_block_heartbeats_and_stop_cancels_it(self):
        node = peer('one', 'CONNECTED')
        started, cancelled, repeated = asyncio.Event(), asyncio.Event(), asyncio.Event()
        calls = []
        async def reconnect(ident):
            calls.append(ident)
            if len(calls) >= 3: repeated.set()
        async def work(ident):
            started.set()
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: [node], get_node=lambda _: node), reconnect,
            SimpleNamespace(publish=lambda *args: None), interval=.01, work=work)
        await runner.start()
        try:
            await asyncio.wait_for(started.wait(), 1)
            await asyncio.wait_for(repeated.wait(), 1)
        finally:
            await runner.stop()
        self.assertTrue(cancelled.is_set())

    async def test_revocation_during_network_call_never_claims_verified(self):
        node = peer('one')
        async def reconnect(ident): node.node_state = 'REVOKED'
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: [node], get_node=lambda _: node), reconnect,
            SimpleNamespace(publish=lambda *args: None))
        await runner.tick()
        self.assertNotIn('one', runner.status)

    async def test_repeated_failures_back_off_to_bounded_two_minutes(self):
        node = peer('one')
        now, calls = [0], []
        async def reconnect(ident):
            calls.append(now[0])
            raise OSError('offline')
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: [node], get_node=lambda _: node), reconnect,
            SimpleNamespace(publish=lambda *args: None), clock=lambda: now[0])
        for when in (0, 15, 45, 105, 225):
            now[0] = when
            await runner.tick()
            now[0] = when + 1
            await runner.tick()
        self.assertEqual(calls, [0, 15, 45, 105, 225])
        self.assertEqual(node.granted_capabilities, [])

    async def test_queued_analysis_revalidates_expired_membership_before_start(self):
        nodes = {ident: peer(ident, 'CONNECTED') for ident in ('one', 'two', 'three')}
        calls, release, occupied = [], asyncio.Event(), asyncio.Event()
        async def reconnect(ident): pass
        async def work(ident):
            calls.append(ident)
            if len(calls) == 2: occupied.set()
            await release.wait()
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: list(nodes.values()), get_node=nodes.get),
            reconnect, SimpleNamespace(publish=lambda *args: None), work=work)
        try:
            await runner.tick()
            await asyncio.wait_for(occupied.wait(), 1)
            nodes['three'].connection_metadata['membership_expires_at'] = 1
            release.set()
            await asyncio.sleep(.02)
            self.assertEqual(calls, ['one', 'two'])
        finally:
            await runner.stop()


if __name__ == '__main__': unittest.main()
