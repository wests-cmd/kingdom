from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from backend.security.http_auth import require_owner
from backend.cluster.node_registry import node_registry
from backend.cluster.hierarchy import CommandHierarchy
from backend.storage.db import db
from backend.api import engine

router = APIRouter(prefix='/hierarchy', dependencies=[Depends(require_owner)])
hierarchy = CommandHierarchy(db, node_registry, engine.events.publish)


class GroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    captain: str = Field(max_length=128)
    members: list[str] = Field(min_length=1, max_length=100)
    flags: list[str] = Field(default_factory=list, max_length=12)
    preferred_task_types: list[str] = Field(default_factory=list, max_length=12)


@router.get('')
async def status():
    result=hierarchy.export(engine.swarm.registry.status())
    from backend.cluster.shared_groups import configured,validate_snapshot
    shared=configured()
    if shared.authority():
        try:
            snapshot=await shared.exchange()
            result.update(groups_read_only=False,groups_notice='Shared organizational groups; permissions remain separate.')
        except Exception:
            snapshot=shared.mesh._get('shared_groups')
            try:
                validate_snapshot(snapshot)
                if snapshot['authority_id']!=shared.authority():raise ValueError('Different authority')
            except (ValueError,TypeError,KeyError):snapshot={'groups':[],'version':'','authority_id':shared.authority()}
            result.update(groups_read_only=True,groups_notice='Shared group authority unavailable. The last verified layout is read-only; refresh after it reconnects.')
        view=shared.view(snapshot)
        result.update(groups=view['groups'],groups_version=view['version'],group_authority=view['authority_id'],groups_shared=True)
    return result


from backend.cluster.group_requests import GroupEditRequest


@router.post('/groups/edit')
async def edit_groups(request:GroupEditRequest):
    from backend.cluster.shared_groups import configured
    shared=configured()
    if shared.authority():
        data=request.model_dump()
        data['members']=[shared.mesh.identity.node_id if m=='local' else m for m in data['members']]
        if data['captain']=='local':data['captain']=shared.mesh.identity.node_id
        try:return shared.view(await shared.exchange(data))
        except (ValueError,PermissionError,KeyError) as error:raise HTTPException(409,str(error)) from error
        except Exception as error:
            import httpx
            if isinstance(error,httpx.HTTPError):raise HTTPException(503,'Shared group authority unavailable; no local substitute was saved') from error
            raise
    data=request.model_dump();version=data.pop('version');operation=data.pop('operation')
    try:return hierarchy.edit_groups(version,operation,**data)
    except ValueError as error:raise HTTPException(409,str(error)) from error


class VisibilityRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    offline_hours: int=Field(ge=12,le=240,strict=True)


@router.put('/visibility')
def visibility(request:VisibilityRequest):
    return hierarchy.set_visibility(request.offline_hours)


@router.post('/groups')
def create(request: GroupRequest):
    from backend.cluster.mesh_api import membership
    if membership().config():raise HTTPException(409,'Use the shared diagram group editor for this Kingdom')
    try: return hierarchy.create_group(request.name, request.captain, request.members, request.flags, request.preferred_task_types)
    except ValueError as error: raise HTTPException(400, str(error)) from error


@router.delete('/groups/{ident}')
def delete_group(ident: str):
    from backend.cluster.mesh_api import membership
    if membership().config():raise HTTPException(409,'Use the shared diagram group editor for this Kingdom')
    try: return hierarchy.delete_group(ident)
    except ValueError as error: raise HTTPException(404, str(error)) from error


class TopologyRequest(BaseModel):
    version: int = Field(ge=0, strict=True)
    parents: dict[str, str] = Field(max_length=1000)


@router.put('/topology')
def save_topology(request: TopologyRequest):
    from backend.cluster.topology import TopologyConflict
    nodes = hierarchy.export(engine.swarm.registry.status())['topology']['nodes']
    try:
        return hierarchy.topology.save(request.version, request.parents, nodes)
    except TopologyConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


from backend.cluster.release_status import DesiredRelease, ReleasePreferences
release_preferences = ReleasePreferences(db, engine.events.publish)


@router.get('/releases')
def release_status():
    return release_preferences.status([node.to_dict() for node in hierarchy.computers()])


@router.put('/releases/desired')
def desired_release(request: DesiredRelease):
    return release_preferences.set(request.model_dump())
