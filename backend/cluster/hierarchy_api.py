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
def status(): return hierarchy.export(engine.swarm.registry.status())


class GroupEditRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    version: str=Field(pattern='^[0-9a-f]{64}$')
    operation: str=Field(pattern='^(save|remove|combine|split|unassign)$')
    group_ids: list[str]=Field(default_factory=list,max_length=100)
    name: str=Field(default='',max_length=100)
    captain: str=Field(default='',max_length=128)
    members: list[str]=Field(default_factory=list,max_length=100)
    move: bool=False
    names: list[str]=Field(default_factory=list,max_length=100)
    flags: list[str]=Field(default_factory=list,max_length=12)
    preferred_task_types: list[str]=Field(default_factory=list,max_length=12)


@router.post('/groups/edit')
def edit_groups(request:GroupEditRequest):
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
    try: return hierarchy.create_group(request.name, request.captain, request.members, request.flags, request.preferred_task_types)
    except ValueError as error: raise HTTPException(400, str(error)) from error


@router.delete('/groups/{ident}')
def delete_group(ident: str):
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
