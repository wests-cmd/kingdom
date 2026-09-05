from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

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


class LocalLANTransport(NodeTransport):
    def connect(self, endpoint: str) -> bool:
        self.endpoint = endpoint
        return True

    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "delivered", "transport": "LAN", "endpoint": getattr(self, "endpoint", "local")}

    def disconnect(self) -> bool:
        return True


class DirectWANTransport(NodeTransport):
    def connect(self, endpoint: str) -> bool:
        self.endpoint = endpoint
        return True

    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "delivered", "transport": "DirectWAN", "endpoint": getattr(self, "endpoint", "direct")}

    def disconnect(self) -> bool:
        return True


class OverlayTailscaleTransport(NodeTransport):
    def __init__(self):
        try:
            from backend.integrations.tailscale.connector import TailscaleConnector
            self.connector = TailscaleConnector()
        except ImportError:
            self.connector = None

    def connect(self, endpoint: str) -> bool:
        if self.connector:
            res = self.connector.connect()
            return res.get("connected", False)
        return False

    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "delivered", "transport": "TailscaleOverlay"}

    def disconnect(self) -> bool:
        return True
