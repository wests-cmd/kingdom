"""Computers are Knights; local software workers are Knight Apprentices."""
import json
import socket
import time
from uuid import uuid4


class CommandHierarchy:
    def __init__(self, database, registry, publisher):
        self.db, self.registry, self.publish = database, registry, publisher
        from backend.cluster.topology import CoordinationTopology
        self.topology = CoordinationTopology(database, publisher)
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS command_groups(id TEXT PRIMARY KEY,data_json TEXT NOT NULL)'); conn.commit()
            conn.execute('CREATE TABLE IF NOT EXISTS swarm_preferences(id TEXT PRIMARY KEY,data_json TEXT NOT NULL)'); conn.commit()

    def group_version(self):
        from backend.cluster.team_editing import version
        return version(self.groups())

    def edit_groups(self, expected, operation, **kwargs):
        from backend.cluster.team_editing import edit
        return edit(self, expected, operation, **kwargs)

    def visibility(self):
        with self.db.get_connection() as conn:
            row=conn.execute("SELECT data_json FROM swarm_preferences WHERE id='visibility'").fetchone()
        return json.loads(row[0]) if row else {'offline_hours':168}

    def set_visibility(self, hours):
        import math
        if type(hours) not in (float,int) or not math.isfinite(hours) or not 12<=hours<=240:
            raise ValueError('Choose an offline timeout between 12 hours and 10 days')
        value={'offline_hours':hours}
        with self.db.get_connection() as conn:
            conn.execute("INSERT INTO swarm_preferences VALUES('visibility',?) ON CONFLICT(id) DO UPDATE SET data_json=excluded.data_json",(json.dumps(value),));conn.commit()
        self.publish('hierarchy.visibility_changed',value)
        return value

    def visible_computers(self):
        import math
        cutoff=time.time()-self.visibility()['offline_hours']*3600
        def recent(node):
            stamp=node.last_heartbeat or node.created_at
            return type(stamp) in (int,float) and math.isfinite(stamp) and stamp>=cutoff
        return [n for n in self.computers() if n.node_state in {'APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'} and recent(n)]

    def groups(self):
        with self.db.get_connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT data_json FROM command_groups')]

    def computers(self):
        return [node for node in self.registry.list_nodes() if not node.is_local and node.public_identity and node.fingerprint]

    def create_group(self, name, captain, members, flags=None, preferred_task_types=None):
        flags, preferred_task_types = flags or [], preferred_task_types or []
        for values in (flags, preferred_task_types):
            if len(values) > 12 or any(not isinstance(value, str) or not value.strip() or len(value) > 80 for value in values) or len(set(values)) != len(values):
                raise ValueError('Use at most 12 distinct nonempty labels, up to 80 characters each')
        known = {node.node_id: node for node in self.computers()}
        if not name.strip() or len(name) > 100 or not members or len(set(members)) != len(members) or len(members) > 100:
            raise ValueError('Supply a group name and distinct member computers')
        if captain not in members or any(ident not in known or known[ident].node_state not in {'APPROVED','CONNECTED'} for ident in members):
            raise ValueError('Captain and members must be approved paired computers')
        group = {'id': uuid4().hex, 'name': name.strip(), 'captain': captain, 'members': members, 'flags': flags, 'preferred_task_types': preferred_task_types, 'preference_scope': 'planning_only', 'created_at': time.time(), 'created_by': 'owner'}
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if any(set(json.loads(row[0])['members']).intersection(members) for row in conn.execute('SELECT data_json FROM command_groups')):
                raise ValueError('Knights already belong to a team; confirm a move in the diagram')
            conn.execute('INSERT INTO command_groups VALUES(?,?)', (group['id'], json.dumps(group))); conn.commit()
        self.publish('hierarchy.group_created', {'group_id': group['id'], 'captain': captain, 'members': members})
        return group

    def delete_group(self, ident):
        with self.db.get_connection() as conn:
            deleted = conn.execute('DELETE FROM command_groups WHERE id=?', (ident,)).rowcount
            conn.commit()
        if not deleted:
            raise ValueError('Team no longer exists')
        self.publish('hierarchy.group_deleted', {'group_id': ident})
        return {'deleted': ident}

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
        from backend.cluster.apprentice_inventory import aggregate_inventories
        computers = self.computers()
        participating = self.visible_computers()
        inventory = aggregate_inventories(apprentices, [node.to_dict() for node in participating])
        from backend.cluster.topology import topology_nodes
        graph = self.topology.read(topology_nodes(apprentices, participating, inventory['remote_apprentices']))
        groups=self.groups()
        from backend.cluster.team_editing import version
        result = {'commander': {'id': 'owner', 'computer': socket.gethostname(), 'authority': 'All groups; owner approval and capability policy remain highest'},
                'topology': graph,
                'inventory': inventory,
                'knights': [node.to_dict() for node in participating],
                'archived_knights': [node.to_dict() for node in computers if node not in participating],
                'apprentices': [{**item, 'entity_type': 'knight_apprentice', 'host': socket.gethostname()} for item in apprentices],
                'groups': groups, 'groups_version':version(groups), 'visibility':self.visibility(), 'definitions': {'knight': 'A connected computer', 'knight_apprentice': 'An agent or bot on a computer',
                'knight_captain': 'An approved computer commanding its own group', 'commander': 'Highest control over approved computers and groups'}}
        from backend.cluster.computer_display import display_hierarchy
        return display_hierarchy(result, self.db)


def offload_candidate(registry, capability, members=None, outcomes=None, tool=None, busy_nodes=None, estimated_seconds=None, decision_report=None):
    now = time.time()
    candidates = []
    selector_candidates = []
    for node in registry.list_nodes():
        if node.node_id in (busy_nodes or set()): continue
        if node.is_local or not node.public_identity or node.node_state not in {'APPROVED','CONNECTED'} or now - node.last_heartbeat > 45 or node.health != 'healthy' or node.current_task:
            continue
        if capability not in node.granted_capabilities or (members is not None and node.node_id not in members): continue
        load = node.connection_metadata.get('load_metrics', {})
        cpu, memory = load.get('cpu_percent', 100), load.get('memory_percent', 100)
        if not all(isinstance(value, (int, float)) and 0 <= value < 85 for value in (cpu, memory)): continue
        from backend.cluster.power_policy import power_budget
        estimate = estimated_seconds if estimated_seconds is not None else (180 if capability=='process.execute' else 10)
        if not power_budget(load.get('power'),estimate)['allowed']:continue
        # Adapt only from controller-persisted outcomes for the same operation.
        # Worker claims, model text and advertised capabilities are not success.
        successes = failures = 0
        for task in (outcomes or [])[:100]:
            meta = task.get('metadata') or {}
            if meta.get('execution_target') != 'remote' or (tool and meta.get('tool') != tool): continue
            result = task.get('result') or {}
            if (result.get('executed_by') or task.get('assigned_knight')) != node.node_id: continue
            if task.get('status', '').lower() in {'completed', 'succeeded'} and (result.get('verification') or {}).get('state') == 'VERIFIED':
                successes += 1
            elif task.get('status', '').lower() == 'failed':
                failures += 1
        # A smoothed failure penalty cannot override eligibility or capacity.
        penalty = 60 * failures / (successes + failures + 2)
        candidates.append((cpu + memory + penalty, node.node_id))
        selector_candidates.append({'id': node.node_id, 'fit': 1, 'idle': 1,
                                    'memory_headroom': 1-memory/100,
                                    'success': successes/(successes+failures) if successes+failures else 0,
                                    'load': (cpu+memory)/200})
    if decision_report is not None:
        from backend.models.decision_selectors import recommend_knights
        try:
            decision_report.update(recommend_knights(selector_candidates, independent_tasks=1,
                                                     owner_parallel_limit=1))
            decision_report['affects_execution'] = False
        except (OSError, ValueError, KeyError, TypeError):
            decision_report.update({'mode': 'unavailable', 'affects_execution': False})
    return min(candidates)[1] if candidates else None
