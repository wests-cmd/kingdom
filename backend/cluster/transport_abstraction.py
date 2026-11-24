"""Legacy transport names retained for compatibility, not operational routes.

Real peer exchanges go through federation_api and the signed RPC verifier.
An unimplemented transport must never report delivery or attempt an unapproved
network route. A route adapter may be enabled only after real authenticated
round-trip and failure tests exist.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class NodeTransport(ABC):
    @abstractmethod
    def connect(self, endpoint: str) -> bool:
        pass

    @abstractmethod
    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass


class UnavailableTransport(NodeTransport):
    """Fail closed without opening sockets, invoking tools or fabricating receipts."""

    transport = "unavailable"

    def connect(self, endpoint: str) -> bool:
        return False

    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "not_sent", "transport": self.transport,
                "reason": "authenticated_transport_not_implemented"}

    def disconnect(self) -> bool:
        return True  # No connection or external process was opened.


class LocalLANTransport(UnavailableTransport):
    transport = "LAN"


class DirectWANTransport(UnavailableTransport):
    transport = "DirectWAN"


class OverlayTailscaleTransport(UnavailableTransport):
    transport = "TailscaleOverlay"
