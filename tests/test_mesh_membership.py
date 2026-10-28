import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.cluster.identity import KingdomIdentity
from backend.cluster.mesh_membership import MeshMembership
from backend.cluster.node_registry import NodeRegistry, NodeState
from backend.storage.db import Database
from backend.storage.repository import KnightRepository


class MembershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 2000000000.0
        self.events = []
        self.a, self.b, self.c = [KingdomIdentity(kingdom_id=name) for name in ['authority', 'first', 'newcomer']]
        self.meshes = {}
        for identity in [self.a, self.b, self.c]:
            database = Database(Path(self.tmp.name) / (identity.node_id + '.db'))
            registry = NodeRegistry(KnightRepository(database))
            self.meshes[identity.node_id] = MeshMembership(database, registry, identity,
                SimpleNamespace(publish=lambda *args: self.events.append(args)), clock=lambda: self.now)
        self.authority = self.meshes[self.a.node_id]
        self.authority.configure(self.a.node_id, 'https://authority.example')
        self.enroll(self.b)
        self.enroll(self.c)

    def register(self, mesh, identity, grants=None):
        mesh.registry.register_discovered_node({'id': identity.node_id, 'public_identity': identity.get_public_identity(),
            'fingerprint': identity.fingerprint, 'node_state': 'APPROVED', 'is_local': False,
            'kingdom_id': mesh.identity.node_id, 'granted_capabilities': grants or [],
            'connection_metadata': {'kingdom_endpoint': 'https://' + identity.node_id + '.example'}})

    def enroll(self, identity):
        mesh = self.meshes[identity.node_id]
        self.register(self.authority, identity)
        self.register(mesh, self.a)
        mesh.configure(self.a.node_id, 'https://' + identity.node_id + '.example')

    def distribute(self):
        for identity in [self.b, self.c]:
            mesh = self.meshes[identity.node_id]
            mesh.receive(self.a.node_id, self.authority.export(identity.node_id))

    def test_single_authority_approval_builds_every_reciprocal_pair_without_grants(self):
        self.distribute()
        for identity in [self.b, self.c]:
            mesh = self.meshes[identity.node_id]
            other = self.c if identity == self.b else self.b
            node = mesh.registry.get_node(other.node_id)
            self.assertEqual(node.node_state, 'APPROVED')
            self.assertEqual(node.granted_capabilities, [])
            self.assertEqual(node.last_heartbeat, 0)
            self.assertEqual(node.connection_metadata['mesh_authority'], self.a.node_id)

    def test_revocation_propagates_and_local_revocation_cannot_be_undone(self):
        self.distribute()
        self.authority.registry.update_node_state(self.c.node_id, NodeState.REVOKED)
        mesh = self.meshes[self.b.node_id]
        mesh.receive(self.a.node_id, self.authority.export(self.b.node_id))
        self.assertEqual(mesh.registry.get_node(self.c.node_id).node_state, 'REVOKED')
        self.authority.registry.update_node_state(self.c.node_id, NodeState.APPROVED)
        mesh.receive(self.a.node_id, self.authority.export(self.b.node_id))
        self.assertEqual(mesh.registry.get_node(self.c.node_id).node_state, 'REVOKED')

    def test_restart_retains_authority_generation_and_idempotent_reconciliation(self):
        self.distribute()
        mesh = self.meshes[self.b.node_id]
        restarted = MeshMembership(mesh.db, mesh.registry, mesh.identity, mesh.events, clock=lambda: self.now)
        roster = self.authority.export(self.b.node_id)
        restarted.receive(self.a.node_id, roster)
        self.assertEqual(restarted._get('received')['generation'], roster['generation'])
        stale = copy.deepcopy(roster)
        stale['generation'] -= 1
        with self.assertRaises(ValueError): restarted.receive(self.a.node_id, stale)
        conflicting = copy.deepcopy(roster)
        conflicting['members'][0]['endpoint'] = 'https://changed.example'
        with self.assertRaises(ValueError): restarted.receive(self.a.node_id, conflicting)

    def test_bad_authority_expiration_duplicates_and_substitution_rejected_before_writes(self):
        mesh = self.meshes[self.b.node_id]
        roster = self.authority.export(self.b.node_id)
        with self.assertRaises(ValueError): mesh.receive('imposter', roster)
        bad_cases = []
        bad = copy.deepcopy(roster); bad['expires_at'] = self.now - 1; bad_cases.append(bad)
        bad = copy.deepcopy(roster); bad['members'].append(bad['members'][0]); bad_cases.append(bad)
        bad = copy.deepcopy(roster)
        for row in bad['members']:
            if row['identity']['node_id'] == self.b.node_id:
                replacement = KingdomIdentity(kingdom_id=self.b.node_id)
                row['identity'] = replacement.get_public_identity()
        bad_cases.append(bad)
        for bad in bad_cases:
            with self.assertRaises(ValueError): mesh.receive(self.a.node_id, bad)
            self.assertIsNone(mesh.registry.get_node(self.c.node_id))

    def test_existing_grants_preserved_and_temporary_membership_keeps_deadline(self):
        mesh = self.meshes[self.b.node_id]
        self.register(mesh, self.c, ['compute'])
        node = self.authority.registry.get_node(self.c.node_id)
        node.connection_metadata['membership_expires_at'] = self.now + 50
        self.authority.registry.repo.save(node.to_dict())
        self.distribute()
        node = mesh.registry.get_node(self.c.node_id)
        self.assertEqual(node.granted_capabilities, ['compute'])
        self.assertEqual(node.connection_metadata['membership_expires_at'], self.now + 50)
        self.now += 51
        mesh.receive(self.a.node_id, self.authority.export(self.b.node_id))
        self.assertEqual(mesh.registry.get_node(self.c.node_id).node_state, 'REVOKED')

    def test_disable_revokes_managed_members_and_is_safe_when_already_disabled(self):
        mesh = self.meshes[self.b.node_id]
        mesh.disable()
        self.assertEqual(mesh.registry.get_node(self.a.node_id).node_state, 'APPROVED')
        mesh.disable()
        mesh.configure(self.a.node_id, 'https://first.example')
        self.distribute()
        mesh.disable()
        self.assertEqual(mesh.registry.get_node(self.c.node_id).node_state, 'REVOKED')

    def test_roster_cannot_extend_a_local_temporary_membership(self):
        mesh = self.meshes[self.b.node_id]
        self.register(mesh, self.c)
        node = mesh.registry.get_node(self.c.node_id)
        node.connection_metadata['membership_expires_at'] = self.now + 10
        mesh.registry.repo.save(node.to_dict())
        self.distribute()
        self.assertEqual(mesh.registry.get_node(self.c.node_id).connection_metadata['membership_expires_at'], self.now + 10)


if __name__ == '__main__': unittest.main()
