"""Atomic organizational edits. Membership never changes execution grants."""
import hashlib
import json
import time
from uuid import uuid4


def version(groups):
    return hashlib.sha256(json.dumps(sorted(groups,key=lambda g:g['id']),sort_keys=True,
                                     separators=(',',':')).encode()).hexdigest()


def edit(service, expected, operation, *, group_ids=(), name='', captain='', members=(),
         move=False, names=(), flags=(), preferred_task_types=()):
    if operation not in {'save','remove','combine','split','unassign'}:
        raise ValueError('Unknown team operation')
    known={node.node_id for node in service.computers()
           if node.node_state in {'APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'}}|{'local'}
    if len(group_ids)>100 or len(set(group_ids))!=len(group_ids):
        raise ValueError('Select distinct teams')
    if len(members)>100 or len(set(members))!=len(members) or any(m not in known for m in members):
        raise ValueError('Select distinct approved Knights')
    for labels in (flags,preferred_task_types):
        if len(labels)>12 or len(set(labels))!=len(labels) or any(not isinstance(v,str) or not v.strip() or len(v)>80 for v in labels):
            raise ValueError('Use up to 12 distinct labels of 80 characters')
    def titled(value):
        if not isinstance(value,str) or not value.strip() or len(value)>100:
            raise ValueError('Supply a team name up to 100 characters')
        return value.strip()
    def new_group(label,people,leader='',template=None):
        return {**(template or {}),'id':uuid4().hex,'name':titled(label),'members':list(people),
                'captain':leader or people[0],'flags':list((template or {}).get('flags',flags)),
                'preferred_task_types':list((template or {}).get('preferred_task_types',preferred_task_types)),
                'preference_scope':'planning_only','created_at':time.time(),'created_by':'owner'}
    def trim(group,removed):
        group['members']=[m for m in group['members'] if m not in removed]
        if group['members'] and group['captain'] not in group['members']:
            group['captain']=group['members'][0]
        return bool(group['members'])
    with service.db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        groups=[json.loads(row[0]) for row in conn.execute('SELECT data_json FROM command_groups ORDER BY rowid')]
        if expected!=version(groups):raise ValueError('Teams changed on another screen; reload before saving')
        by_id={g['id']:g for g in groups}
        selected=[by_id[ident] for ident in group_ids if ident in by_id]
        if len(selected)!=len(group_ids):raise ValueError('A selected team no longer exists')
        if operation=='save':
            if len(selected)>1 or not members or captain not in members:
                raise ValueError('Select members and a leader within this team')
            others=[g for g in groups if g['id'] not in group_ids]
            conflicts=[g for g in others if set(g['members']).intersection(members)]
            if conflicts and not move:raise ValueError('Please confirm moving Knights from their other teams')
            others=[g for g in others if trim(g,set(members))]
            group=new_group(name,members,captain)
            if selected:
                group.update(id=selected[0]['id'],created_at=selected[0]['created_at'])
            groups=others+[group]
        elif operation=='remove':
            if not selected:raise ValueError('Select at least one team')
            groups=[g for g in groups if g['id'] not in group_ids]
        elif operation=='unassign':
            if not members:raise ValueError('Select Knights to remove from teams')
            groups=[g for g in groups if trim(g,set(members))]
        elif operation=='combine':
            if len(selected)<2:raise ValueError('Select at least two teams to combine')
            people=list(dict.fromkeys(m for g in selected for m in g['members']))
            if len(people)>100:raise ValueError('A team can contain at most 100 Knights')
            if any(m not in known for m in people):raise ValueError('Remove revoked Knights before combining')
            if captain and captain not in people:raise ValueError('Leader must belong to the combined team')
            merged=new_group(name,people,captain or selected[0]['captain'])
            for key in ('flags','preferred_task_types'):
                merged[key]=list(dict.fromkeys(v for g in selected for v in g.get(key,[])))
                if len(merged[key])>12:raise ValueError('Combined team exceeds 12 preference labels; edit labels first')
            groups=[g for g in groups if g['id'] not in group_ids]+[merged]
        else:
            if len(selected)!=1 or not 2<=len(names)<=len(selected[0]['members']):
                raise ValueError('Split one team into at least two nonempty teams')
            source=selected[0]
            if any(m not in known for m in source['members']):raise ValueError('Remove revoked Knights before splitting')
            # Round robin puts a remainder into the first teams, preserving order.
            parts=[new_group(label,source['members'][i::len(names)],template=source) for i,label in enumerate(names)]
            groups=[g for g in groups if g['id'] not in group_ids]+parts
        used=set()
        for group in groups:
            if used.intersection(group['members']):raise ValueError('Resolve overlapping legacy teams before this edit')
            used.update(group['members'])
        conn.execute('DELETE FROM command_groups')
        conn.executemany('INSERT INTO command_groups VALUES(?,?)',[(g['id'],json.dumps(g)) for g in groups])
        conn.commit()
    revision=version(groups)
    service.publish('hierarchy.groups_changed',{'operation':operation,'group_ids':[g['id'] for g in groups], 'version':revision})
    return {'groups':groups,'version':revision}
