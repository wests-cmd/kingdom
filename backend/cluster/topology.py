"""Owner-edited coordination lines; never tool grants or agent relocation."""
import json
import time


class TopologyConflict(ValueError):
    pass


class CoordinationTopology:
    def __init__(self, database, publisher):
        self.db, self.publish = database, publisher
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS coordination_topology (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, parents TEXT NOT NULL)')
            conn.execute("INSERT OR IGNORE INTO coordination_topology VALUES(1,0,'{}')")

    def read(self, nodes):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT version,parents FROM coordination_topology WHERE id=1').fetchone()
        saved = json.loads(row['parents'])
        known = {node['id'] for node in nodes}
        # Removed or revoked entities are never resurrected by saved layout.
        parents = {node['id']: saved.get(node['id'], node['default_parent']) for node in nodes}
        parents = {ident: parent if parent in known or parent == 'kingdom' else 'kingdom' for ident, parent in parents.items()}
        return {'version': row['version'], 'nodes': nodes, 'parents': parents,
                'meaning': 'Coordination only. Hosting, capability grants and autonomy do not change.'}

    def save(self, version, parents, nodes):
        known = {node['id'] for node in nodes}
        if set(parents) != known or len(known) > 1000:
            raise ValueError('Refresh the graph; supply each currently known entity exactly once')
        for ident, parent in parents.items():
            if parent != 'kingdom' and parent not in known:
                raise ValueError('Unknown coordination parent')
            visited, current = set(), ident
            while current != 'kingdom':
                if current in visited:
                    raise ValueError('Coordination lines cannot contain a cycle')
                visited.add(current)
                current = parents[current]
        with self.db.get_connection() as conn:
            result = conn.execute('UPDATE coordination_topology SET version=version+1,parents=? WHERE id=1 AND version=?',
                                  (json.dumps(parents, sort_keys=True), version))
            if result.rowcount != 1:
                raise TopologyConflict('Another editor changed the graph. Reload before saving.')
        self.publish('hierarchy.topology_saved', {'version': version + 1, 'entities': len(known), 'saved_at': time.time()})
        return self.read(nodes)


def topology_nodes(apprentices, computers, remote):
    nodes = [{'id': 'local', 'kind': 'knight', 'label': 'This Knight', 'default_parent': 'kingdom', 'host': 'local'}]
    nodes += [{'id': node.node_id, 'kind': 'knight', 'label': node.hostname or node.node_id,
               'default_parent': 'kingdom', 'host': node.node_id} for node in computers]
    nodes += [{'id': 'local/' + agent['id'], 'kind': 'apprentice', 'label': 'Apprentices-' + agent.get('role', agent['id']),
               'default_parent': 'local', 'host': 'local'} for agent in apprentices]
    nodes += [{'id': agent['scoped_id'], 'kind': 'apprentice', 'label': 'Apprentices-' + agent.get('role', agent['id']),
               'default_parent': agent['kingdom_id'], 'host': agent['kingdom_id']} for agent in remote]
    return nodes
