"""Owner-only passive adapter discovery; never grants authority or executes tools."""
from fastapi import APIRouter, Depends, HTTPException
from backend.security.http_auth import require_owner
from backend.integrations.acp_adapters import ACPToolManager

router = APIRouter(prefix="/integrations/adapters", dependencies=[Depends(require_owner)])


def manager() -> ACPToolManager:
    return ACPToolManager()


@router.get("")
def list_adapters():
    service = manager()
    return {
        "tools": service.list_tools(),
        "models": service.list_models(),
        "credential_isolation": "No external credentials collected",
        "execution_authority_granted": False,
    }


@router.get("/{tool_id}")
def inspect_adapter(tool_id: str):
    try:
        return manager().inspect_tool(tool_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Adapter not found") from exc


@router.get("/{tool_id}/connectivity")
def inspect_connectivity(tool_id: str):
    try:
        return manager().verify_connectivity(tool_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Adapter not found") from exc
