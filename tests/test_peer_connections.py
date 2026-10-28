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
        async def reconnect(ident):
            calls.append(ident)
            if len(calls) == 1: raise OSError('offline')
        runner = module.PeerConnections(SimpleNamespace(list_nodes=lambda: [node], get_node=lambda _: node), reconnect,
                                        SimpleNamespace(publish=lambda *args: None))
        await runner.tick()
        self.assertEqual(runner.status['one'], 'retrying')
        await runner.tick()
        self.assertEqual(runner.status['one'], 'verified')
        await runner.start()
        task = runner.task
        await runner.start()
        self.assertIs(runner.task, task)
        await runner.stop()
        self.assertTrue(task.done())
        self.assertIsNone(runner.task)


if __name__ == '__main__': unittest.main()
