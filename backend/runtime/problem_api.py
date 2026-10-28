from fastapi import APIRouter,Depends
from backend.security.http_auth import require_owner

router=APIRouter(prefix='/problems',dependencies=[Depends(require_owner)])
_service=None

def service():
    global _service
    if _service is None:
        from backend.runtime.work_programme_api import service as programmes
        from backend.runtime.work_backlog_api import service as backlog
        from backend.api import engine
        from backend.storage.db import db
        from backend.runtime.problem_bot import ProblemBot
        _service=ProblemBot(db,programmes(),backlog(),engine.events)
    return _service

@router.get('')
def status():return service().snapshot()
