"""Owner-only proposal inbox. Does not expose owner tools directly to ChatGPT."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner
from backend.runtime.chat_proposals import ChatProposals, ChatTask

router = APIRouter(prefix='/chat-proposals', dependencies=[Depends(require_owner)])


def service():
    from backend.storage.db import db
    from backend.models.profiles import ModelProfiles
    from backend.runtime.request_api import service as requests
    from backend.events.event_bus import event_bus
    return ChatProposals(db, ModelProfiles(db), requests(), event_bus.publish)


def call(method, *args):
    try:
        return getattr(service(), method)(*args)
    except KeyError as error:
        raise HTTPException(404, 'Proposal or local profile not found') from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


class Reply(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=12000)


@router.post('', status_code=201)
def create(body: ChatTask):
    return call('create', body)


@router.get('/{ident}')
def get(ident: str):
    return call('get', ident)


@router.post('/{ident}/reply')
def reply(ident: str, body: Reply):
    return call('submit', ident, body.text)


@router.post('/{ident}/review', status_code=202)
def review(ident: str):
    return call('queue_review', ident)
