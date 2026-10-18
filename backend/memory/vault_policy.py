"""Generic storage placement and least-information retrieval policy.

Placement is a plan, not a claim that replication or migration has occurred.
Payment instruments remain with a payment provider, never in ordinary AI notes.
"""
import hashlib
import re

MODES={'standalone','balanced','central'}


def readers(value):
    if value is None:return []
    if not isinstance(value,list) or len(value)>32 or any(not isinstance(role,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',role) for role in value):
        raise ValueError('Use explicit Apprentice roles')
    return sorted(set(value))


def can_read(document,role=None):
    allowed=readers(document.get('allowed_roles',[]))
    return role=='owner' or not allowed or role in allowed


def reject_payment_details(body):
    # Never turn general model memory into a payment-card store. Provider-issued
    # references and display-only last four digits are the supported contract.
    for match in re.finditer(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)',body):
        digits=''.join(char for char in match.group() if char.isdigit())
        if not 13<=len(digits)<=19:continue
        total=0
        for index,char in enumerate(reversed(digits)):
            value=int(char)
            if index%2:value=value*2-9 if value*2>9 else value*2
            total+=value
        if total%10==0:raise ValueError('Use a payment provider reference, not card details in model memory')
    if re.search(r'''(?i)\b(?:cvv|cvc|card security code)["']?\s*[:=]\s*["']?\d{3,4}\b''',body):
        raise ValueError('Payment security codes do not belong in AI memory')


def placement(key,knights,mode='standalone',central_id=None,copies=1):
    if mode not in MODES or type(copies) is not int or not 1<=copies<=8:
        raise ValueError('Choose standalone, balanced or central storage and bounded copies')
    if not isinstance(key,str) or not isinstance(knights,list):
        raise ValueError('Supply a document key and Knight inventory')
    seen=set()
    for node in knights:
        if not isinstance(node,dict) or not isinstance(node.get('id'),str) or not node['id'] or node['id'] in seen:
            raise ValueError('Knight identities must be unique')
        seen.add(node['id'])
        for field in ('free_bytes','used_bytes'):
            value=node.get(field,0)
            if type(value) is not int or value<0:
                raise ValueError('Vault capacity must be a nonnegative integer')
    eligible=[node for node in knights if node.get('available') is True and node.get('free_bytes',0)>0]
    if not eligible:raise ValueError('No available vault destination')
    if mode=='central':
        selected=[node for node in eligible if node['id']==central_id]
        if not selected:raise ValueError('The selected central vault is unavailable')
    elif mode=='standalone':
        if len(knights)!=1:raise ValueError('Standalone layout requires exactly one Knight')
        selected=eligible
    else:
        # Prefer less-utilized vaults; deterministic ties avoid personal host IDs
        # being embedded in policy. Rebalancing remains an explicit transfer job.
        selected=sorted(eligible,key=lambda node:(node.get('used_bytes',0)/(node['free_bytes']+node.get('used_bytes',0)),hashlib.sha256((key+'\0'+node['id']).encode()).hexdigest()))[:copies]
    return {'mode':mode,'archive_knights':[node['id'] for node in selected],
            'status':'planned','notice':'A placement plan does not perform data transfer or grant access.'}
