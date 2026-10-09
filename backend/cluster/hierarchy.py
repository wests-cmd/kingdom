"""Computers are Knights; local software workers are Knight Apprentices."""
import json
import socket
import time
from uuid import uuid4


class CommandHierarchy:
    def __init__(self, database, registry, publisher):
        self.db, self.registry, self.publish = database, registry, publisher
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS command_groups(id TEXT PRIMARY KEY,data_json TEXT NOT NULL)'); conn.commit()

    def groups(self):
        with self.db.get_connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT data_json FROM command_groups')]

    def computers(self):
        return [node for node in self.registry.list_nodes() if not node.is_local and node.public_identity and node.fingerprint]

    def create_group(self, name, captain, members):
        known = {node.node_id: node for node in self.computers()}
        if not name.strip() or len(name) > 100 or not members or len(set(members)) != len(members) or len(members) > 100:
            raise ValueError('Supply a group name and distinct member computers')
        if captain not in members or any(ident not in known or known[ident].node_state not in {'APPROVED','CONNECTED'} for ident in members):
            raise ValueError('Captain and members must be approved paired computers')
        group = {'id': uuid4().hex, 'name': name, 'captain': captain, 'members': members, 'created_at': time.time(), 'created_by': 'owner'}
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO command_groups VALUES(?,?)', (group['id'], json.dumps(group))); conn.commit()
        self.publish('hierarchy.group_created', {'group_id': group['id'], 'captain': captain, 'members': members})
        return group

    def authorize_assignment(self, actor, group_id, target):
        group = next((item for item in self.groups() if item['id'] == group_id), None)
        if not group or (actor != 'owner' and actor != group['captain']) or target not in group['members']:
            raise PermissionError('A Captain can assign work only within its own group')
        known = {node.node_id: node for node in self.computers()}
        if target not in known or known[target].node_state not in {'APPROVED','CONNECTED'}:
            raise PermissionError('Target computer is not currently approved')
        if actor != 'owner' and (actor not in known or known[actor].node_state not in {'APPROVED','CONNECTED'}):
            raise PermissionError('Captain approval is no longer active')
        return group

    def export(self, apprentices):
        return {'commander': {'id': 'owner', 'computer': socket.gethostname(), 'authority': 'All groups; owner approval and capability policy remain highest'},
                'knights': [node.to_dict() for node in self.computers()],
                'apprentices': [{**item, 'entity_type': 'knight_apprentice', 'host': socket.gethostname()} for item in apprentices],
                'groups': self.groups(), 'definitions': {'knight': 'A connected computer', 'knight_apprentice': 'An agent or bot on a computer',
                'knight_captain': 'An approved computer commanding its own group', 'commander': 'Highest control over approved computers and groups'}}


def offload_candidate(registry, capability, members=None):
    now = time.time()
    candidates = []
    for node in registry.list_nodes():
        if node.is_local or not node.public_identity or node.node_state not in {'APPROVED','CONNECTED'} or now - node.last_heartbeat > 45 or node.health != 'healthy' or node.current_task:
            continue
        if capability not in node.granted_capabilities or (members is not None and node.node_id not in members): continue
        load = node.connection_metadata.get('load_metrics', {})
        cpu, memory = load.get('cpu_percent', 100), load.get('memory_percent', 100)
        if not all(isinstance(value, (int, float)) and 0 <= value < 85 for value in (cpu, memory)): continue
        candidates.append((cpu + memory, node.node_id))
    return min(candidates)[1] if candidates else None
