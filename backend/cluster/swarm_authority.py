"""Human-configured role boundary. Never infer authority from a model or heartbeat.

This registry is controller-scoped until a shared authority service is configured.
Do not merge competing registries or treat a disconnected King as absent.
"""
import hashlib
import hmac
import json
import secrets


class SwarmAuthority:
    def __init__(self, database, publisher):
        self.db, self.publish = database, publisher
        with database.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS swarm_authority(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, data TEXT NOT NULL)')
            conn.execute('INSERT OR IGNORE INTO swarm_authority VALUES(1,0,?)',
                         (json.dumps({'king':None,'commanders':{},'ghost_hash':None,'policies':{}}),))
            conn.commit()

    def _read(self, conn):
        row=conn.execute('SELECT revision,data FROM swarm_authority WHERE id=1').fetchone()
        return row[0],json.loads(row[1])

    def status(self):
        with self.db.get_connection() as conn:
            revision,data=self._read(conn)
        return {'revision':revision,'king':data['king'],'commanders':data['commanders'],
                'ghost_enabled':bool(data['ghost_hash']),'policies':data['policies'],
                'scope':'controller','federated':False}

    @staticmethod
    def _allowed(data, actor, group_id=None):
        if actor in {'owner','ghost'} or actor==data['king']:
            return
        grant=data['commanders'].get(actor)
        if not grant or (data['king'] is not None and not grant['delegated']):
            raise PermissionError('Only the King or a delegated Commander can make this change')
        if group_id is not None and group_id not in grant['groups']:
            raise PermissionError('Commander authority is limited to assigned groups')

    def authenticate_ghost(self, token):
        if not isinstance(token,str) or not 40<=len(token)<=128:
            return False
        with self.db.get_connection() as conn:
            _,data=self._read(conn)
        digest=hashlib.sha256(token.encode()).hexdigest()
        return bool(data['ghost_hash']) and hmac.compare_digest(digest,data['ghost_hash'])

    def change(self, actor, expected, operation, arguments, *, known, groups):
        """Actor comes from owner auth or verified signed RPC, never JSON input.

        Ghost tokens are resolved inside the transaction so revocation cannot race
        a queued mutation. No secret enters events or public status.
        """
        group_map={g['id']:g for g in groups}
        secret=None
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            revision,data=self._read(conn)
            if type(expected) is not int or revision!=expected:
                raise ValueError('Authority settings changed; refresh before saving')
            if isinstance(actor,tuple) and actor[0]=='ghost_token':
                digest=hashlib.sha256(actor[1].encode()).hexdigest()
                if not data['ghost_hash'] or not hmac.compare_digest(digest,data['ghost_hash']):
                    raise PermissionError('Ghost Key is disabled or revoked')
                actor='ghost'
            if not isinstance(actor,str):raise PermissionError('Authenticated principal required')
            if actor not in {'owner','ghost',data['king']}:
                grant=data['commanders'].get(actor)
                if actor not in known or not grant or not any(g in group_map and actor in group_map[g]['members'] for g in grant['groups']):
                    raise PermissionError('Commander membership is no longer active')
            if operation in {'king','commander'}:
                if actor not in {'owner','ghost',data['king']}:
                    raise PermissionError('Only the owner or King can appoint authority roles')
                if operation=='king':
                    target=arguments.get('knight')
                    if target is not None and target not in known:raise ValueError('Choose a known approved Knight')
                    if target!=data['king']:
                        # Delegations never survive a crown transfer/removal.
                        for grant in data['commanders'].values():grant['delegated']=False
                    data['king']=target
                else:
                    target=arguments.get('knight');assigned=arguments.get('groups')
                    if target not in known or not isinstance(assigned,list) or len(assigned)>100 or any(g not in group_map or target not in group_map[g]['members'] for g in assigned):
                        raise ValueError('Commander must belong to each assigned group')
                    delegated=arguments.get('delegated',False)
                    if type(delegated) is not bool:raise ValueError('Delegation must be explicitly on or off')
                    if assigned:data['commanders'][target]={'groups':sorted(set(assigned)),'delegated':delegated}
                    else:data['commanders'].pop(target,None)
            elif operation in {'ghost_create','ghost_revoke'}:
                self._allowed(data,actor)
                # Commanders may create a Ghost Key only when no King exists.
                if actor not in {'owner','ghost',data['king']} and data['king'] is not None:
                    raise PermissionError('Only the King can set up a Ghost Key while a King exists')
                if operation=='ghost_create':
                    if data['ghost_hash']:raise ValueError('Revoke the existing Ghost Key before creating another')
                    secret=secrets.token_urlsafe(48)
                    data['ghost_hash']=hashlib.sha256(secret.encode()).hexdigest()
                else:data['ghost_hash']=None
            elif operation=='group_policy':
                group_id=arguments.get('group_id')
                if group_id not in group_map:raise ValueError('Group no longer exists')
                self._allowed(data,actor,group_id)
                if actor in data['commanders'] and actor not in {'owner','ghost',data['king']} and actor not in group_map[group_id]['members']:
                    raise PermissionError('Commander no longer belongs to this group')
                level=arguments.get('autonomy_ceiling');caps=arguments.get('capabilities')
                if type(level) is not int or not 0<=level<=5:raise ValueError('Choose an autonomy ceiling from 0 to 5')
                if not isinstance(caps,list) or len(caps)>64 or any(not isinstance(c,str) or not c or len(c)>100 for c in caps):
                    raise ValueError('Supply bounded capability names')
                data['policies'][group_id]={'autonomy_ceiling':level,'capabilities':sorted(set(caps))}
            else:raise ValueError('Unknown authority operation')
            conn.execute('UPDATE swarm_authority SET revision=?,data=? WHERE id=1',(revision+1,json.dumps(data)))
            conn.commit()
        self.publish('hierarchy.authority_changed',{'revision':revision+1,'operation':operation,'actor':actor})
        result=self.status()
        if secret:result['ghost_key']=secret
        return result

    def permits(self, target, capability, level, groups):
        """Restrictions only: cannot grant a capability or waive any approval.

        A stricter group ceiling holds dispatch until the controller policy is
        compatible. Lowering the ceiling must not silently alter another group.
        """
        state=self.status()
        for group in groups:
            policy=state['policies'].get(group['id'])
            if target in group['members'] and policy is not None:
                if policy['autonomy_ceiling']==0 or level>policy['autonomy_ceiling'] or capability not in policy['capabilities']:
                    return False
        return True
