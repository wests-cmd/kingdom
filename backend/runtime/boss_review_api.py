"""Owner-visible accountability for the service-owned Boss receipt reviewer."""
from fastapi import APIRouter, Depends
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/boss-reviews', dependencies=[Depends(require_owner)])
_service = None


def service():
    global _service
    if _service is None:
        from backend.storage.db import db
        from backend.api import engine
        from backend.runtime.work_programme_api import service as programmes
        from backend.runtime.work_backlog_api import service as backlog
        from backend.runtime.boss_reviews import BossReviews
        _service = BossReviews(db, programmes(), backlog(), engine)
    return _service


@router.get('')
def listing():
    return service().list()
