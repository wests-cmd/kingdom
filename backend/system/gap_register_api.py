"""API endpoints for the Kingdom Gap Register."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from backend.storage.db import db
from backend.system.gap_register import GapRegister
from backend.system.gap_backlog_bridge import register_missing_capabilities
from backend.runtime.work_backlog_api import service as backlog_service
from backend.security.http_auth import require_owner

router = APIRouter(prefix="/system/gap-register", tags=["Gap Register"], dependencies=[Depends(require_owner)])
register = GapRegister(db)


class GapEvidenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_evidence: str = Field(min_length=1, max_length=2000)
    status: Optional[str] = Field(default=None, pattern=r"^(missing|partial|verified|blocked)$")


@router.get("")
def list_gaps():
    items = register.list()
    verified_count = sum(1 for item in items if item["status"] == "verified")
    partial_count = sum(1 for item in items if item["status"] == "partial")
    missing_count = sum(1 for item in items if item["status"] == "missing")
    blocked_count = sum(1 for item in items if item["status"] == "blocked")
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "verified": verified_count,
            "partial": partial_count,
            "missing": missing_count,
            "blocked": blocked_count
        }
    }


@router.get("/{ident}")
def get_gap(ident: str):
    item = register.get(ident)
    if not item:
        raise HTTPException(status_code=404, detail="Gap register entry not found")
    return item


@router.put("/{ident}/evidence")
def update_gap_evidence(ident: str, update: GapEvidenceUpdate):
    try:
        return register.update_evidence(ident, update.test_evidence, update.status)
    except KeyError:
        raise HTTPException(status_code=404, detail="Gap register entry not found")


@router.post("/sync-backlog")
def sync_gaps_to_backlog(project: str = "kingdom", limit: int = 20):
    """Idempotently register incomplete capabilities into the work backlog."""
    try:
        backlog = backlog_service()
        items = register_missing_capabilities(register, backlog, project=project, limit=limit)
        return {
            "synced_count": len(items),
            "items": items
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
