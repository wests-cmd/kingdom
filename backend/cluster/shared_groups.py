"""Signed organizational group edits through the existing membership authority.

These messages never carry credentials, capability grants or autonomy changes.
Each approved Knight's authenticated owner can edit this organizational layout.
"""
import json
import secrets
from backend.cluster.team_editing import version


def remap(groups, source, target):
    return [{**g,'members':[target if ident==source else ident for ident in g['members']],
             'captain':target if g['captain']==source else g['captain']} for g in groups]


def validate_snapshot(value):
    if not isinstance(value,dict) or set(value)!={'groups','version','authority_id'}:
        raise ValueError('Invalid shared group snapshot')
    groups=value['groups']
    if not isinstance(groups,list) or len(groups)>100 or len(json.dumps(value))>262144:
        raise ValueError('Group snapshot exceeds its limit')
    used=set();ids=set()
    for g in groups:
        if (not isinstance(g,dict) or not isinstance(g.get('id'),str) or g['id'] in ids
                or not isinstance(g.get('name'),str) or not 1<=len(g['name'])<=100
                or not isinstance(g.get('members'),list) or not 1<=len(g['members'])<=100
                or any(not isinstance(m,str) or not 1<=len(m)<=128 or m=='local' for m in g['members'])
                or len(set(g['members']))!=len(g['members']) or used.intersection(g['members'])
                or g.get('captain') not in g['members']):
            raise ValueError('Invalid shared group identity or membership')
        ids.add(g['id']);used.update(g['members'])
    if value['version']!=version(groups):raise ValueError('Shared group version does not match its content')
    return value


class SharedGroups:
    def __init__(self,mesh,hierarchy):
        self.mesh,self.hierarchy=mesh,hierarchy

    def authority(self):
        return self.mesh.config().get('authority_id')

    def local_snapshot(self):
        ident=self.mesh.identity.node_id
        if self.authority()!=ident:raise ValueError('Only the configured authority stores shared groups')
        groups=remap(self.hierarchy.groups(),'local',ident)
        return validate_snapshot({'groups':groups,'version':version(groups),'authority_id':ident})

    def receive(self,sender,request):
        """Called only with transport-verified sender and replay-checked payload."""
        if self.authority()!=self.mesh.identity.node_id:
            raise ValueError('This Knight is not the shared group authority')
        node=self.mesh.registry.get_node(sender)
        if not node or node.node_state not in {'APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'}:
            raise PermissionError('Shared group requests require current approved membership')
        if not isinstance(request,dict) or set(request)!={'request_id','edit'} or not isinstance(request['request_id'],str) or not 1<=len(request['request_id'])<=100:
            raise ValueError('Invalid group request')
        result=self.edit(request['edit']) if request['edit'] is not None else self.local_snapshot()
        return {'request_id':request['request_id'],'snapshot':result}

    def edit(self,data):
        from backend.cluster.group_requests import GroupEditRequest
        parsed=GroupEditRequest.model_validate(data).model_dump()
        raw=self.hierarchy.groups()
        if version(remap(raw,'local',self.mesh.identity.node_id))!=parsed.pop('version'):
            raise ValueError('Groups changed on another Knight; refresh before saving')
        operation=parsed.pop('operation')
        parsed['members']=['local' if m==self.mesh.identity.node_id else m for m in parsed['members']]
        if parsed['captain']==self.mesh.identity.node_id:parsed['captain']='local'
        result=self.hierarchy.edit_groups(version(raw),operation,**parsed)
        groups=remap(result['groups'],'local',self.mesh.identity.node_id)
        return validate_snapshot({'groups':groups,'version':version(groups),'authority_id':self.mesh.identity.node_id})

    async def exchange(self,edit=None):
        authority=self.authority()
        if not authority:raise ValueError('Shared membership is not configured')
        if authority==self.mesh.identity.node_id:
            return self.edit(edit) if edit is not None else self.local_snapshot()
        from backend.cluster.transport import RPCSecureTransport
        from backend.cluster.peer_endpoints import endpoint
        from backend.cluster.mesh_api import mesh_tls
        import httpx
        peer=self.mesh.registry.get_node(authority)
        if not peer or peer.node_state not in {'APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'}:
            raise PermissionError('Shared group authority is no longer approved')
        correlation=secrets.token_hex(16)
        transport=RPCSecureTransport(self.mesh.identity)
        message=transport.create_signed_message(authority,'mesh_group_request',{'request_id':correlation,'edit':edit})
        address=endpoint((peer.connection_metadata or {})['kingdom_endpoint'])
        async with httpx.AsyncClient(timeout=8,follow_redirects=False,trust_env=False,verify=mesh_tls()) as client:
            response=await client.post(address+'/nodes/rpc',json=message);response.raise_for_status()
            if len(response.content)>262144:raise ValueError('Group response exceeds its limit')
            reply=response.json()
        if reply.get('sender_id')!=authority or reply.get('msg_type')!='mesh_group_result':
            raise ValueError('Unexpected shared group response identity')
        verified=transport.verify_and_unwrap_message(reply,expected_target_id=self.mesh.identity.node_id)
        if not verified.get('valid') or verified['payload'].get('request_id')!=correlation:
            raise ValueError('Group response signature or request binding failed')
        snapshot=validate_snapshot(verified['payload']['snapshot'])
        if snapshot['authority_id']!=authority:raise ValueError('Unexpected group authority')
        self.mesh._set('shared_groups',snapshot)
        return snapshot

    def view(self,snapshot):
        return {'groups':remap(snapshot['groups'],self.mesh.identity.node_id,'local'),
                'version':snapshot['version'],'authority_id':snapshot['authority_id']}


def configured():
    from backend.cluster.mesh_api import membership
    from backend.cluster.hierarchy_api import hierarchy
    return SharedGroups(membership(),hierarchy)
