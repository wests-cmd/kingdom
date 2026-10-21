"""Separate an identity-pinned archive from bounded per-Kingdom read memory.

The configured archive must already exist. Missing media never silently creates
a replacement archive on the OS disk. Remote synchronization is separate.
"""
import json
import os
import time
from pathlib import Path

from backend.memory.portable_vault import PortableVault, identifier
from backend.storage.db import Database


class VaultUnavailable(OSError):
    pass


class TieredVault:
    def __init__(self, database, publish=None, root=None, vault_id=None, cache_bytes=None):
        self.local = database
        self.publish = publish
        self.root = Path(root) if root else None
        self.vault_id = vault_id
        self.cache_bytes = 8*1024*1024 if cache_bytes is None else cache_bytes
        if type(self.cache_bytes) is not int or not 0 <= self.cache_bytes <= 64*1024*1024:
            raise ValueError('Hot memory must be between zero and 64 MB')
        if self.root and (not self.root.is_absolute() or not isinstance(vault_id,str) or not vault_id.strip()):
            raise ValueError('External vault requires an absolute root and pinned identity')
        with database.get_connection() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS vault_hot_cache(project TEXT,id TEXT,document TEXT,size INTEGER,touched REAL,PRIMARY KEY(project,id))')
            connection.commit()

    def _archive(self):
        if not self.root:
            return PortableVault(self.local,self.publish)
        marker = self.root/'.kingdom-vault-id'
        try:
            if self.root.is_symlink() or marker.is_symlink() or marker.read_text().strip()!=self.vault_id:
                raise VaultUnavailable('Configured vault identity is absent or different')
        except (FileNotFoundError,PermissionError) as error:
            raise VaultUnavailable('Configured vault media is unavailable') from error
        return PortableVault(Database(self.root/'vault.sqlite3'),self.publish)

    def status(self):
        try:
            self._archive();online=True
        except OSError:
            online=False
        with self.local.get_connection() as connection:
            count,size=connection.execute('SELECT COUNT(*),COALESCE(SUM(size),0) FROM vault_hot_cache').fetchone()
        return {'archive':'external' if self.root else 'local','online':online,
                'cache_documents':count,'cache_bytes':size,'cache_limit_bytes':self.cache_bytes,
                'notice':'Cached reads are marked with their age. Offline archive writes are refused; no silent replacement vault is created.'}

    def _remember(self,document):
        document={key:value for key,value in document.items() if key!='cache'}
        encoded=json.dumps(document,ensure_ascii=False);size=len(encoded.encode())
        with self.local.get_connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('DELETE FROM vault_hot_cache WHERE project=? AND id=?',(document['project'],document['id']))
            if size<=self.cache_bytes:
                connection.execute('INSERT INTO vault_hot_cache VALUES(?,?,?,?,?)',(document['project'],document['id'],encoded,size,time.time()))
            while connection.execute('SELECT COALESCE(SUM(size),0) FROM vault_hot_cache').fetchone()[0]>self.cache_bytes:
                connection.execute('DELETE FROM vault_hot_cache WHERE rowid=(SELECT rowid FROM vault_hot_cache ORDER BY touched,project,id LIMIT 1)')
            connection.commit()
        return document

    def get(self,project,ident):
        identifier(project);identifier(ident)
        try:
            return self._remember(self._archive().get(project,ident))
        except VaultUnavailable:
            with self.local.get_connection() as connection:
                row=connection.execute('SELECT document,touched FROM vault_hot_cache WHERE project=? AND id=?',(project,ident)).fetchone()
            if not row:raise
            return {**json.loads(row[0]),'cache':{'offline':True,'age_seconds':max(0,time.time()-row[1]),'authoritative':False}}

    def cached(self,project):
        with self.local.get_connection() as connection:
            rows=connection.execute('SELECT document,touched FROM vault_hot_cache WHERE project=? ORDER BY touched DESC',(identifier(project),)).fetchall()
        offline=not self.status()['online']
        return [{**json.loads(row[0]),'cache':{'offline':offline,'age_seconds':max(0,time.time()-row[1]),'authoritative':False}} for row in rows]

    def put(self,*args,**kwargs):
        return self._remember(self._archive().put(*args,**kwargs))

    def search(self,project,query,reader_role=None):
        identifier(project)
        try:
            return [self._remember(doc) for doc in self._archive().search(project,query,reader_role=reader_role)]
        except VaultUnavailable:
            import re
            terms=set(re.findall(r'\w+',query.lower()))
            with self.local.get_connection() as connection:
                rows=connection.execute('SELECT id FROM vault_hot_cache WHERE project=? ORDER BY touched DESC',(project,)).fetchall()
            docs=[self.get(project,row[0]) for row in rows]
            from backend.memory.vault_policy import can_read
            return [doc for doc in docs if can_read(doc,reader_role) and terms.intersection(re.findall(r'\w+',doc['body'].lower()))][:20]

    def trash(self,project,ident,expected_revision):
        result=self._archive().trash(project,ident,expected_revision)
        with self.local.get_connection() as connection:
            connection.execute('DELETE FROM vault_hot_cache WHERE project=? AND id=?',(project,ident));connection.commit()
        return result

    def restore(self,*args,**kwargs):
        return self._remember(self._archive().restore(*args,**kwargs))

    def export(self,*args,**kwargs):return self._archive().export(*args,**kwargs)
    def import_files(self,*args,**kwargs):return self._archive().import_files(*args,**kwargs)
    def rebuild_index(self,*args,**kwargs):return self._archive().rebuild_index(*args,**kwargs)


def configured_vault(database,publish=None):
    return TieredVault(database,publish,root=os.getenv('KINGDOM_VAULT_ROOT'),
                       vault_id=os.getenv('KINGDOM_VAULT_ID'),
                       cache_bytes=int(os.getenv('KINGDOM_HOT_CACHE_BYTES',str(8*1024*1024))))
