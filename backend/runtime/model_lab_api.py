from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from backend.security.http_auth import require_owner
from backend.runtime.model_lab import ModelLabService, PreparationRequest, Strict, hardware_snapshot

router = APIRouter(prefix='/model-lab', dependencies=[Depends(require_owner)])
_service = None


def service():
    global _service
    if _service is None:
        from backend.api import engine
        from backend.storage.db import db
        _service = ModelLabService(engine, db)
    return _service


class EvaluationRequest(Strict):
    argv: list[str] = Field(min_length=1, max_length=40)
    report_path: str = Field(min_length=1, max_length=300)


def invoke(action, *args):
    try:
        return action(*args)
    except KeyError as error:
        raise HTTPException(404, 'Model preparation job not found') from error
    except (ValueError, OSError) as error:
        raise HTTPException(409, str(error)) from error


@router.get('')
def jobs():
    import shutil
    return {'jobs': service().list(), 'hardware': hardware_snapshot(), 'heretic_executable': shutil.which('heretic'),
            'notice': 'Optional local preparation. Models are not downloaded automatically; no model is trained or promoted without verified artifact and evaluation evidence.'}


@router.post('', status_code=201)
def create(request: PreparationRequest):
    return invoke(service().create, request)


@router.get('/{ident}')
def get(ident: str): return invoke(service().get, ident)


@router.post('/{ident}/start')
def start(ident: str): return invoke(service().start, ident)


@router.post('/{ident}/refresh')
def refresh(ident: str): return invoke(service().refresh, ident)


@router.post('/{ident}/evaluate')
def evaluate(ident: str, request: EvaluationRequest): return invoke(service().evaluate, ident, request.argv, request.report_path)


@router.post('/{ident}/promote')
def promote(ident: str): return invoke(service().promote, ident)


@router.post('/{ident}/rollback')
def rollback(ident: str): return invoke(service().rollback, ident)
