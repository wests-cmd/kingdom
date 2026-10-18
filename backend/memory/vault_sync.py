"""Explicit project grants and atomic, conflict-detecting document replication.

Transport signatures authenticate peers; pairing alone never grants memory access.
Replicas are local SQLite records, never shared database files. Deletions require
an explicit local action and are not silently propagated.
"""
import hashlib
import json
import time
from backend.memory.portable_vault import PortableVault, identifier, clean_metadata, clean_text
from backend.memory.vault_policy import readers, reject_payment_details


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def canonical_document(doc):
    identifier(doc['project']);identifier(doc['id'])
    body=doc['body']
    if not isinstance(body,str) or len(body.encode())>262144:raise ValueError('Document exceeds limit')
    metadata=clean_metadata({key:doc.get(key,default) for key,default in [('provenance',{}),('receipts',[]),('allowed_roles',[])]})
    metadata['allowed_roles']=readers(metadata['allowed_roles']);metadata['trust']='untrusted'
    reject_payment_details(json.dumps({'body':body,**metadata}))
    if clean_text(body)!=body or len(json.dumps(metadata,allow_nan=False).encode())>32768:raise ValueError('Unsafe or oversized document')
    revision=doc.get('revision',1)
    if type(revision) is not int or revision<1:raise ValueError('Invalid source revision')
    return {'project':doc['project'],'id':doc['id'],'revision':revision,'body':body,**metadata}


class VaultSync:
    def __init__(self,database,vault,publish=None):
        self.db,self.vault,self.publish=database,vault,publish or (lambda *args:None)
        with database.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS vault_sync_grants(peer TEXT,project TEXT,direction TEXT,roles TEXT,PRIMARY KEY(peer,project,direction))')
            conn.execute('CREATE TABLE IF NOT EXISTS vault_sync_outbox(peer TEXT,batch TEXT,project TEXT,ids TEXT,receipt TEXT,created REAL,PRIMARY KEY(peer,batch))')
            conn.commit()

    def pending(self,peer,payload):
        self.validate_payload(payload)
        self.authorize(peer,payload['project'],'send',payload['documents'])
        ids=sorted(doc['id'] for doc in payload['documents'])
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO vault_sync_outbox VALUES(?,?,?,?,NULL,?) ON CONFLICT(peer,batch) DO NOTHING',(peer,payload['batch'],payload['project'],json.dumps(ids),time.time()))
            conn.commit()

    def accept_receipt(self,peer,batch,project,receipt,local_id):
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT project,ids FROM vault_sync_outbox WHERE peer=? AND batch=?',(peer,batch)).fetchone()
            if not row or row['project']!=project:raise ValueError('No matching locally prepared transfer')
            if not isinstance(receipt,dict) or receipt.get('peer')!=local_id or receipt.get('project')!=project or receipt.get('batch')!=batch or receipt.get('trust')!='untrusted':raise ValueError('Receipt identity, batch or project mismatch')
            applied=receipt.get('applied');unchanged=receipt.get('unchanged')
            if not isinstance(applied,list) or not isinstance(unchanged,list) or any(not isinstance(value,str) for value in applied+unchanged) or sorted(applied+unchanged)!=json.loads(row['ids']):raise ValueError('Receipt does not cover the prepared document identities')
            conn.execute('UPDATE vault_sync_outbox SET receipt=? WHERE peer=? AND batch=?',(json.dumps(receipt,allow_nan=False),peer,batch));conn.commit()
        self.publish('vault.sync_receipt_verified',{'peer':peer,'project':project,'batch':batch})
        return {'status':'replicated','receipt':receipt}

    def transfer_status(self,peer,batch):
        with self.db.get_connection() as conn:
            row=conn.execute('SELECT project,receipt,created FROM vault_sync_outbox WHERE peer=? AND batch=?',(peer,batch)).fetchone()
        if not row:raise KeyError(batch)
        return {'peer':peer,'batch':batch,'project':row['project'],'created':row['created'],'status':'replicated' if row['receipt'] else 'prepared','receipt':json.loads(row['receipt']) if row['receipt'] else None}

    def grant(self,peer,project,direction,roles):
        identifier(peer);identifier(project)
        if direction not in {'send','receive'}:raise ValueError('Select send or receive')
        roles=readers(roles)
        with self.db.get_connection() as conn:
            conn.execute('INSERT OR REPLACE INTO vault_sync_grants VALUES(?,?,?,?)',(peer,project,direction,json.dumps(roles)));conn.commit()
        self.publish('vault.sync_grant_changed',{'peer':peer,'project':project,'direction':direction})
        return {'peer':peer,'project':project,'direction':direction,'allowed_roles':roles}

    def revoke(self,peer,project,direction):
        with self.db.get_connection() as conn:
            conn.execute('DELETE FROM vault_sync_grants WHERE peer=? AND project=? AND direction=?',(peer,project,direction));conn.commit()
        self.publish('vault.sync_grant_revoked',{'peer':peer,'project':project,'direction':direction})
        return {'revoked':True,'notice':'Existing replicas are retained; revoke or delete them explicitly on each owner-controlled Knight.'}

    def authorize(self,peer,project,direction,documents):
        with self.db.get_connection() as conn:
            row=conn.execute('SELECT roles FROM vault_sync_grants WHERE peer=? AND project=? AND direction=?',(peer,project,direction)).fetchone()
        if not row:raise PermissionError('Explicit peer and project vault grant required')
        roles=set(json.loads(row[0]))
        if any(not set(doc['allowed_roles']).issubset(roles) for doc in documents):raise PermissionError('Restricted document exceeds granted roles')

    def prepare(self,peer,project,ids=None):
        identifier(project)
        files=self.vault.export(project)
        if ids is not None:
            if not isinstance(ids,list) or len(ids)>100:raise ValueError('At most 100 document identities')
            wanted={identifier(ident)+'.md' for ident in ids}
            if wanted-set(files):raise ValueError('Selected document does not exist')
            files={name:value for name,value in files.items() if name in wanted}
        docs=[]
        for markdown in files.values():
            header,_,body=markdown.partition('\n');meta=json.loads(header[len('<!-- kingdom-vault '):-4])
            docs.append(canonical_document({**meta,'body':body}))
        self.authorize(peer,project,'send',docs)
        payload={'project':project,'documents':docs}
        payload['batch']=digest(payload)
        self.validate_payload(payload)
        return payload

    @staticmethod
    def validate_payload(payload):
        if not isinstance(payload,dict) or set(payload)!={'project','documents','batch'}:raise ValueError('Invalid sync envelope')
        project=identifier(payload['project']);docs=payload['documents']
        if not isinstance(docs,list) or len(docs)>100 or len(json.dumps(payload,allow_nan=False).encode())>2*1024*1024:raise ValueError('Sync batch exceeds 100 documents or 2 MB')
        docs=[canonical_document(doc) for doc in docs]
        if any(doc['project']!=project for doc in docs) or len({doc['id'] for doc in docs})!=len(docs):raise ValueError('Project mismatch or duplicate document')
        if payload['batch']!=digest({'project':project,'documents':docs}):raise ValueError('Batch checksum mismatch')
        return docs

    def receive(self,peer,payload):
        docs=self.validate_payload(payload);project=payload['project'];batch=payload['batch']
        self.authorize(peer,project,'receive',docs)
        # Evict cached versions before applying ACL changes. A failed transfer may
        # lose only disposable cache entries; it never broadens access.
        if hasattr(self.vault,'local'):
            with self.vault.local.get_connection() as cache:
                cache.executemany('DELETE FROM vault_hot_cache WHERE project=? AND id=?',[(project,doc['id']) for doc in docs]);cache.commit()
        # Archive unavailable is an explicit failure; never write cached substitutes.
        archive=self.vault._archive() if hasattr(self.vault,'_archive') else self.vault
        result={'peer':peer,'project':project,'batch':batch,'applied':[],'unchanged':[],'trust':'untrusted'}
        # Ledger and document changes use one transaction even when the archive is
        # on removable media. ATTACH is not used: receipts live beside replicas.
        with archive.db.get_connection() as conn:
            conn.executescript('''CREATE TABLE IF NOT EXISTS vault_replica_heads(peer TEXT,project TEXT,id TEXT,source_hash TEXT,local_hash TEXT,source_revision INTEGER,PRIMARY KEY(peer,project,id));
            CREATE TABLE IF NOT EXISTS vault_replica_receipts(peer TEXT,batch TEXT,result TEXT,PRIMARY KEY(peer,batch));''')
            conn.execute('BEGIN IMMEDIATE')
            saved=conn.execute('SELECT result FROM vault_replica_receipts WHERE peer=? AND batch=?',(peer,batch)).fetchone()
            if saved:
                for doc in docs:
                    row=conn.execute('SELECT body,metadata FROM portable_vault WHERE project=? AND id=?',(project,doc['id'])).fetchone()
                    current=canonical_document({'project':project,'id':doc['id'],'body':row['body'],**json.loads(row['metadata'])}) if row else None
                    content=lambda value:{key:item for key,item in value.items() if key!='revision'}
                    if current is None or digest(content(current))!=digest(content(doc)):raise ValueError('Historical receipt no longer matches current replica; resolve conflict')
                return {**json.loads(saved[0]),'replayed':True}
            for doc in docs:
                ident=doc['id'];source_hash=digest({key:value for key,value in doc.items() if key!='revision'})
                old=conn.execute('SELECT * FROM portable_vault WHERE project=? AND id=?',(project,ident)).fetchone()
                if conn.execute('SELECT 1 FROM portable_vault_trash WHERE project=? AND id=?',(project,ident)).fetchone():raise ValueError('Replica conflicts with local trash')
                head=conn.execute('SELECT source_hash,local_hash,source_revision FROM vault_replica_heads WHERE peer=? AND project=? AND id=?',(peer,project,ident)).fetchone()
                old_doc=canonical_document({'project':project,'id':ident,'body':old['body'],**json.loads(old['metadata'])}) if old else None
                old_hash=digest({key:value for key,value in old_doc.items() if key!='revision'}) if old_doc else None
                if head and (doc['revision']<head['source_revision'] or (doc['revision']==head['source_revision'] and source_hash!=head['source_hash'])):raise ValueError('Stale or conflicting source revision')
                if old and old_hash!=source_hash and (not head or old_hash!=head['local_hash']):raise ValueError('Local edit conflicts with incoming replica; resolve explicitly')
                if not old and head:raise ValueError('Replica was removed locally; restore explicitly')
                if old_hash==source_hash:result['unchanged'].append(ident)
                else:
                    metadata={key:value for key,value in doc.items() if key not in {'project','id','body','revision'}}
                    conn.execute('INSERT OR REPLACE INTO portable_vault VALUES(?,?,?,?,?,?)',(project,ident,old['revision']+1 if old else 1,doc['body'],json.dumps(metadata,sort_keys=True),time.time()))
                    PortableVault._index(conn,project,ident,doc['body']);result['applied'].append(ident)
                conn.execute('INSERT OR REPLACE INTO vault_replica_heads VALUES(?,?,?,?,?,?)',(peer,project,ident,source_hash,source_hash,doc['revision']))
            conn.execute('INSERT INTO vault_replica_receipts VALUES(?,?,?)',(peer,batch,json.dumps(result)))
            conn.commit()
        self.publish('vault.replicated',{'peer':peer,'project':project,'batch':batch,'applied':len(result['applied'])})
        return result
