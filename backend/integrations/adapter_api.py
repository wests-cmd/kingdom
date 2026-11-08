"""REST API endpoints for Adapter Capability Discovery and Beginner Readiness.

Guarded by owner authentication: requires authenticated owner and trusted origin.
Exposes installed, supported, observed, and unavailable states, capabilities,
and beginner setup guides without collecting external credentials, executing binaries,
or mutating persistent storage/vault keys.
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.security.http_auth import require_owner
from backend.integrations.acp_adapters import (
    ACPToolManager,
    AdapterListResponse,
    ToolInspectionResponse,
    ToolConnectivityResponse,
)

router = APIRouter(prefix="/integrations/adapters", dependencies=[Depends(require_owner)])
_manager: ACPToolManager | None = None


def get_manager() -> ACPToolManager:
    global _manager
    if _manager is None:
        _manager = ACPToolManager()
    return _manager


@router.get("", response_model=AdapterListResponse)
def list_adapters() -> AdapterListResponse:
    """List all supported external coding tools and model capabilities with discovery details."""
    mgr = get_manager()
    return AdapterListResponse(
        tools=mgr.list_tools(),
        models=mgr.list_models(),
        credential_isolation="Strict: no browser cookies or external credentials extracted",
        execution_authority_granted=False,
    )


@router.get("/{tool_id}", response_model=ToolInspectionResponse)
def inspect_adapter(tool_id: str) -> ToolInspectionResponse:
    """Inspect exact capabilities, installation status, and setup instructions for an adapter."""
    mgr = get_manager()
    try:
        return mgr.inspect_tool(tool_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Adapter '{tool_id}' not found")


@router.get("/{tool_id}/connectivity", response_model=ToolConnectivityResponse)
def verify_connectivity(tool_id: str) -> ToolConnectivityResponse:
    """Verify tool connectivity, permissions, and planner availability without executing binaries."""
    mgr = get_manager()
    try:
        return mgr.verify_connectivity(tool_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Adapter '{tool_id}' not found")
