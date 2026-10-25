import json
import tempfile
import unittest
from pathlib import Path
from backend.storage.db import Database
from backend.cluster.swarm_authority import SwarmAuthority


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Database(Path(self.tmp.name)/'state.db');self.events=[]
        self.service=SwarmAuthority(self.db,lambda *a:self.events.append(a))
        self.groups=[{'id':'a','members':['c','x']},{'id':'b','members':['d','y']}]
        self.known={'k','c','d','x','y'}

    def change(self,op,args={},actor='owner',revision=None):
        return self.service.change(actor,self.service.status()['revision'] if revision is None else revision,
                                   op,args,known=self.known,groups=self.groups)

    def test_default_has_no_king_ghost_or_implicit_commander(self):
        self.assertIsNone(self.service.status()['king'])
        self.assertFalse(self.service.status()['ghost_enabled'])
        with self.assertRaises(PermissionError):self.change('group_policy',{'group_id':'a','autonomy_ceiling':3,'capabilities':['compute']},'c')

    def test_commander_scope_delegation_and_disconnected_king(self):
        self.change('commander',{'knight':'c','groups':['a']})
        policy={'group_id':'a','autonomy_ceiling':3,'capabilities':['compute']}
        self.change('group_policy',policy,'c')
        with self.assertRaises(PermissionError):self.change('group_policy',{**policy,'group_id':'b'},'c')
        self.change('king',{'knight':'k'})
        with self.assertRaises(PermissionError):self.change('group_policy',policy,'c')
        self.change('commander',{'knight':'c','groups':['a'],'delegated':True},'k')
        self.change('group_policy',policy,'c')
        with self.assertRaises(PermissionError):self.change('ghost_create',{},'c')
        self.change('king',{'knight':'x'},'k')
        with self.assertRaises(PermissionError):self.change('group_policy',policy,'c')

    def test_ghost_single_secret_hash_revocation_and_restart(self):
        self.change('commander',{'knight':'c','groups':['a']})
        result=self.change('ghost_create',{},'c');token=result['ghost_key']
        self.assertTrue(self.service.authenticate_ghost(token))
        self.assertNotIn('ghost_key',self.service.status())
        with self.db.get_connection() as conn:stored=conn.execute('SELECT data FROM swarm_authority').fetchone()[0]
        self.assertNotIn(token,stored);self.assertNotIn(token,json.dumps(self.events))
        with self.assertRaises(ValueError):self.change('ghost_create')
        other=SwarmAuthority(self.db,lambda *a:None)
        self.assertTrue(other.authenticate_ghost(token))
        self.change('king',{'knight':'k'},('ghost_token',token))
        self.change('ghost_revoke')
        self.assertFalse(other.authenticate_ghost(token))
        with self.assertRaises(PermissionError):self.change('king',{'knight':'x'},('ghost_token',token))

    def test_stale_writes_cannot_create_second_key_or_overwrite_king(self):
        revision=self.service.status()['revision'];self.change('king',{'knight':'k'})
        with self.assertRaises(ValueError):self.change('king',{'knight':'x'},revision=revision)
        self.assertEqual(self.service.status()['king'],'k')

    def test_removed_member_loses_commander_authority(self):
        self.change('commander',{'knight':'c','groups':['a']})
        self.groups[0]['members'].remove('c')
        with self.assertRaises(PermissionError):self.change('ghost_create',{},'c')

    def test_group_ceiling_is_restrictive_not_a_new_grant(self):
        self.change('group_policy',{'group_id':'a','autonomy_ceiling':3,'capabilities':['compute']})
        self.assertTrue(self.service.permits('x','compute',3,self.groups))
        self.assertFalse(self.service.permits('x','compute',5,self.groups))
        self.assertFalse(self.service.permits('x','process.execute',3,self.groups))
        self.assertTrue(self.service.permits('y','process.execute',5,self.groups))


if __name__=='__main__':unittest.main()
