"""Unused-by-default combined-tree verifier seam; no programme gate is relaxed.

A preparation record, component verdict or caller boolean cannot satisfy this
separate signature domain. A protected producer and operator installation are
still required before any live combined result can exist.
"""
import base64
import hashlib
import json
import math
import re
import sqlite3
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field

CONTEXT = b'kingdom.combined-patch-test.v1\0'
BINDING = {'programme_id','section_key','project','source','base_revision','contract_id',
           'contract_sha256','ordered_inputs_sha256','preparation_sha256','combined_tree_sha256'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class CombinedContract(BaseModel):
    """Exact operator-reviewed test scope, not a model's coverage assessment."""
    model_config = ConfigDict(extra='forbid',strict=True)
    contract_id: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,100}$')
    contract_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    minimum_tests: int = Field(ge=1,le=100000)
    argv: list[str] = Field(min_length=1,max_length=100)


def expected_binding(programme_id, section_key, preparation, contract, component_records, reviewers, *, now=None):
    """Bind current independently reverified components to exact preparation.

    component_records are ordered {'binding': exact current job binding,
    'attestation': retained signed envelope} values from trusted current state.
    No caller-supplied accepted_at or expired-receipt override is supported.
    """
    from backend.runtime.patch_acceptance import verify_attestation
    now = time.time() if now is None else now
    contract = CombinedContract.model_validate(contract).model_dump()
    for value in (programme_id,section_key):
        if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_.-]{1,120}',value):
            raise ValueError('Exact programme and section identities required')
    if any(not isinstance(v,str) or not 1<=len(v)<=1000 for v in contract['argv']):
        raise ValueError('Exact bounded operator integration command required')
    fields = {'format','project','source','base_revision','source_archive_sha256','ordered_inputs',
              'ordered_inputs_sha256','combined_tree_sha256','changed_paths','scope','provenance_sha256'}
    if (not isinstance(preparation,dict) or set(preparation)!=fields
            or preparation['format']!='kingdom.combined-source-preparation.v1'
            or preparation['provenance_sha256']!=digest({k:v for k,v in preparation.items() if k!='provenance_sha256'})
            or not isinstance(component_records,list) or not 2<=len(component_records)<=8
            or len(preparation['ordered_inputs'])!=len(component_records)):
        raise ValueError('Complete exact combined preparation and current component order required')
    pinned, identities = [], set()
    for index,(record,entry) in enumerate(zip(component_records,preparation['ordered_inputs']),1):
        if not isinstance(record,dict) or set(record)!={'binding','attestation'}:
            raise ValueError('Retained component signatures and current bindings required')
        proof = verify_attestation(record['attestation'],record['binding'],reviewers,now=now)
        bound = proof['binding']
        item = {'receipt_id':proof['receipt_id'],'receipt_sha256':digest(record['attestation']),'binding':bound}
        if (set(entry)!={'receipt_id','receipt_sha256','binding','index','reviewer_id','tree_after_patch_sha256'}
                or not re.fullmatch('[a-f0-9]{64}',entry['tree_after_patch_sha256'])
                or entry.get('index')!=index or any(entry.get(k)!=v for k,v in item.items())
                or entry.get('reviewer_id')!=proof['reviewer_id'] or proof['receipt_id'] in identities
                or any(bound[k]!=preparation[k] for k in ('project','source','base_revision'))
                or proof['execution']['source_archive_sha256']!=preparation['source_archive_sha256']
                or contract['contract_sha256']==bound['contract_sha256']):
            raise ValueError('Current component order/source differs or component contract reused as integration')
        identities.add(proof['receipt_id']); pinned.append(item)
    if digest(pinned)!=preparation['ordered_inputs_sha256']:
        raise ValueError('Ordered current receipt input hash changed')
    if preparation['ordered_inputs'][-1]['tree_after_patch_sha256']!=preparation['combined_tree_sha256']:
        raise ValueError('Final ordered preparation tree differs from combined tree')
    binding = {k:preparation[k] for k in ('project','source','base_revision','ordered_inputs_sha256','combined_tree_sha256')}
    binding.update(programme_id=programme_id,section_key=section_key,contract_id=contract['contract_id'],
                   contract_sha256=contract['contract_sha256'],preparation_sha256=preparation['provenance_sha256'])
    return binding


def verify(envelope, binding, contract, preparation, reviewers, *, now=None):
    now = time.time() if now is None else now
    contract = CombinedContract.model_validate(contract).model_dump()
    try:
        if (set(binding)!=BINDING or not isinstance(envelope,dict) or set(envelope)!={'payload','signature'}
                or len(canonical(envelope))>65536
                or any(binding[k]!=preparation[k] for k in ('project','source','base_revision','ordered_inputs_sha256','combined_tree_sha256'))
                or binding['preparation_sha256']!=preparation['provenance_sha256']
                or preparation['provenance_sha256']!=digest({k:v for k,v in preparation.items() if k!='provenance_sha256'})
                or any(not re.fullmatch('[a-f0-9]{64}',binding[k]) for k in
                       ('ordered_inputs_sha256','preparation_sha256','combined_tree_sha256','contract_sha256'))
                or not re.fullmatch('[a-f0-9]{40}',binding['base_revision'])
                or any(not 1<=len(v)<=1000 for v in contract['argv'])):
            raise ValueError('Bounded exact combined envelope required')
        proof=envelope['payload']
        if (set(proof)!={'format','receipt_id','reviewer_id','issued_at','expires_at','binding','execution'}
                or proof['format']!='kingdom.combined-patch-test.v1' or canonical(proof['binding'])!=canonical(binding)
                or binding['contract_id']!=contract['contract_id'] or binding['contract_sha256']!=contract['contract_sha256']):
            raise ValueError('Wrong combined signature domain or exact binding')
        for field in ('receipt_id','reviewer_id'):
            if not re.fullmatch('[A-Za-z0-9_.-]{1,120}',proof[field]):raise ValueError('Bounded proof identity required')
        issued,expiry=proof['issued_at'],proof['expires_at']
        if (any(type(v) not in (int,float) or not math.isfinite(v) for v in (issued,expiry))
                or issued>now+5 or not issued<expiry or expiry<=now or expiry-issued>3600):
            raise ValueError('Current original verdict window required')
        reviewer=reviewers[proof['reviewer_id']]
        for field in ('projects','sources','combined_contracts'):
            if not isinstance(reviewer.get(field),list) or len(reviewer[field])>100 or any(not isinstance(v,str) for v in reviewer[field]):
                raise ValueError('Exact operator-installed combined reviewer scope lists required')
        # Existing component signer registration is deliberately insufficient.
        if (reviewer.get('enabled') is not True or binding['project'] not in reviewer.get('projects',[])
                or binding['source'] not in reviewer.get('sources',[])
                or not isinstance(reviewer.get('combined_contracts'),list)
                or binding['contract_sha256'] not in reviewer['combined_contracts']):
            raise ValueError('Operator-installed combined producer scope required')
        execution=proof['execution']
        fields={'run_id','image_sha256','source_archive_sha256','tested_tree_sha256','argv','test_count',
                'failed_count','exit_code','network_isolated','read_only_source','verdict_origin','cleanup_complete'}
        if (not isinstance(execution,dict) or set(execution)!=fields
                or execution['tested_tree_sha256']!=binding['combined_tree_sha256']
                or execution['source_archive_sha256']!=preparation['source_archive_sha256']
                or execution['argv']!=contract['argv']
                or type(execution['test_count']) is not int or execution['test_count']<contract['minimum_tests']
                or type(execution['failed_count']) is not int or execution['failed_count']!=0
                or type(execution['exit_code']) is not int or execution['exit_code']!=0
                or execution['network_isolated'] is not True or execution['read_only_source'] is not True
                or execution['cleanup_complete'] is not True or execution['verdict_origin']!='external_combined_controller'
                or not isinstance(execution['run_id'],str) or not 1<=len(execution['run_id'])<=120
                or not re.fullmatch('[a-f0-9]{64}',execution['image_sha256'])):
            raise ValueError('Actual exact-tree isolated integration verdict required')
        key=base64.b64decode(reviewer['public_key'],validate=True)
        Ed25519PublicKey.from_public_bytes(key).verify(base64.b64decode(envelope['signature'],validate=True),CONTEXT+canonical(proof))
        return proof
    except Exception as error:
        raise ValueError('No current separately signed combined-tree verdict') from error


class CombinedReceiptStore:
    """Unwired seam. Trusted resolve_current(conn) must read reviewed live state.

    It returns binding, contract and preparation after expected_binding rechecks.
    The callable is internal code, never a configurable model/HTTP callback.
    """
    def __init__(self,database,publish,clock=time.time):
        self.db,self.publish,self.clock=database,publish,clock
        with database.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS combined_receipts(receipt_id TEXT PRIMARY KEY,binding_hash TEXT UNIQUE NOT NULL,envelope_json TEXT NOT NULL)')
            conn.commit()

    def accept(self,envelope,resolve_current):
        from backend.runtime.patch_acceptance import reviewer_registry
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            binding,contract,preparation=resolve_current(conn)
            proof=verify(envelope,binding,contract,preparation,reviewer_registry(),now=self.clock())
            try:
                conn.execute('INSERT INTO combined_receipts VALUES(?,?,?)',(proof['receipt_id'],digest(binding),json.dumps(envelope)))
            except sqlite3.IntegrityError as error:
                raise ValueError('Combined receipt or binding was already consumed') from error
            conn.commit()
        self.publish('combined.receipt_recorded',{'programme_id':binding['programme_id'],'section_key':binding['section_key'],'receipt_id':proof['receipt_id']})
        return {'receipt_id':proof['receipt_id'],'binding':binding,'scope':'Combined verifier record only; no programme advancement or publication'}

    def current(self,resolve_current):
        from backend.runtime.patch_acceptance import reviewer_registry
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            binding,contract,preparation=resolve_current(conn)
            row=conn.execute('SELECT envelope_json FROM combined_receipts WHERE binding_hash=?',(digest(binding),)).fetchone()
            if row is None:return None
            proof=verify(json.loads(row[0]),binding,contract,preparation,reviewer_registry(),now=self.clock())
            return {'receipt_id':proof['receipt_id'],'binding':binding,'scope':'Current separately signed combined verifier record; gate remains unwired'}
