"""Shared schema for owner HTTP and authenticated peer organizational edits."""
from pydantic import BaseModel,ConfigDict,Field


class GroupEditRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    version:str=Field(pattern='^[0-9a-f]{64}$')
    operation:str=Field(pattern='^(save|remove|combine|split|unassign)$')
    group_ids:list[str]=Field(default_factory=list,max_length=100)
    name:str=Field(default='',max_length=100)
    captain:str=Field(default='',max_length=128)
    members:list[str]=Field(default_factory=list,max_length=100)
    move:bool=False
    names:list[str]=Field(default_factory=list,max_length=100)
    flags:list[str]=Field(default_factory=list,max_length=12)
    preferred_task_types:list[str]=Field(default_factory=list,max_length=12)
