"""
Kingdom Knight Standalone Daemon Entrypoint.

Runs as an independent OS process representing a remote or local worker Knight node.
Handles:
1. Persistent Knight Identity generation/loading (KnightIdentity).
2. Pairing invitation request & proof-of-possession signature submission.
3. Status polling until Commander approval (WAITING_FOR_APPROVAL -> APPROVED / CONNECTED).
4. Task queue execution over HTTP/RPC socket endpoints.
5. Heartbeat ping emission & process lifecycle management.
"""

import os
import sys
import time
import json
import argparse
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

from backend.cluster.identity import KnightIdentity
from backend.cluster.transport import RPCSecureTransport, RPCMessage
from backend.cluster.node_registry import NodeState


class KnightDaemon:
    def __init__(
        self,
        node_id: str,
        display_name: str,
        commander_url: str,
        listen_port: int,
        capabilities: List[str],
        data_dir: str = "data"
    ):
        self.node_id = node_id
        self.display_name = display_name
        self.commander_url = commander_url.rstrip("/")
        self.listen_port = listen_port
        self.capabilities = capabilities
        self.data_dir = data_dir

        self.identity = KnightIdentity.get_or_create(
            knight_id=self.node_id,
            display_name=self.display_name,
            filepath=os.path.join(self.data_dir, f"{self.node_id}_identity.json")
        )
        self.transport = RPCSecureTransport(self.identity)
        self.node_state = NodeState.DISCOVERED.value
        self.running = False

    def _http_request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.commander_url}{path}"
        data_bytes = json.dumps(payload).encode("utf-8") if payload else None
        headers = {"Content-Type": "application/json"} if payload else {}

        req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except Exception as exc:
            raise RuntimeError(f"HTTP {method} {url} failed: {str(exc)}")

    def request_pairing(self, pairing_code: str) -> bool:
        cmd_id_res = self._http_request("GET", "/nodes/identity")
        cmd_k_id = cmd_id_res.get("node_id", "KG-MASTER-01")

        msg_to_sign = f"{pairing_code}:{self.identity.node_id}:{cmd_k_id}".encode("utf-8")
        sig_bytes = self.identity.sign_message(msg_to_sign)

        payload = {
            "code": pairing_code,
            "knight_public_identity": self.identity.get_public_identity(),
            "requested_capabilities": self.capabilities,
            "signature": sig_bytes.hex(),
            "is_local": False
        }

        try:
            res = self._http_request("POST", "/nodes/pair", payload)
            if res.get("success"):
                self.node_state = NodeState.PENDING_APPROVAL.value
                return True
            else:
                print(f"[{self.node_id}] Pairing rejected: {res}")
        except Exception as exc:
            print(f"[{self.node_id}] Pairing request failed: {exc}")
        return False

    def check_approval_status(self) -> str:
        try:
            res = self._http_request("GET", f"/nodes/{self.node_id}")
            state = res.get("node_state") or res.get("status")
            if state:
                self.node_state = state
            return self.node_state
        except Exception:
            return self.node_state

    def _get_commander_id(self) -> str:
        try:
            res = self._http_request("GET", "/nodes/identity")
            return res.get("node_id", "KG-MASTER-01")
        except Exception:
            return "KG-MASTER-01"

    def send_rpc(self, msg_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        target_id = self._get_commander_id()
        signed_rpc = self.transport.create_signed_message(target_id=target_id, msg_type=msg_type, payload=payload)
        return self._http_request("POST", "/nodes/rpc", signed_rpc)

    def send_heartbeat(self) -> bool:
        try:
            res = self.send_rpc("heartbeat", {"node_id": self.node_id})
            return res.get("status") == "ok"
        except Exception:
            return False

    def poll_and_execute_task(self) -> Optional[Dict[str, Any]]:
        try:
            res = self.send_rpc("task_poll", {"node_id": self.node_id})
            tasks = res.get("tasks", [])
            if not isinstance(tasks, list):
                return None

            for task in tasks:
                task_id = task["id"]
                fencing_token = task.get("fencing_token", 1)
                prompt = task.get("prompt") or task.get("input", {}).get("prompt", "noop")

                result_payload = {
                    "task_id": task_id,
                    "executed_by": self.node_id,
                    "fencing_token": fencing_token,
                    "output": f"Executed by {self.node_id}: {prompt}",
                    "timestamp": time.time()
                }

                try:
                    self.send_rpc("task_result", result_payload)
                except Exception as exc:
                    print(f"[{self.node_id}] RPC task result error: {exc}")
                return result_payload
        except Exception as exc:
            print(f"[{self.node_id}] RPC task poll error: {exc}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Kingdom Knight Standalone Daemon")
    parser.add_argument("--node-id", required=True, help="Knight Node ID")
    parser.add_argument("--display-name", default="Knight Worker", help="Display Name")
    parser.add_argument("--commander-url", default="http://127.0.0.1:8000", help="Commander Base URL")
    parser.add_argument("--listen-port", type=int, default=8001, help="Knight Local Listen Port")
    parser.add_argument("--capabilities", nargs="*", default=["compute"], help="Advertised Capabilities")
    parser.add_argument("--pairing-code", help="Pairing code for initial enrollment")
    parser.add_argument("--data-dir", default="data", help="Directory for node storage")

    args = parser.parse_args()

    daemon = KnightDaemon(
        node_id=args.node_id,
        display_name=args.display_name,
        commander_url=args.commander_url,
        listen_port=args.listen_port,
        capabilities=args.capabilities,
        data_dir=args.data_dir
    )

    print(f"[{args.node_id}] Daemon starting... ID={daemon.identity.node_id}")

    if args.pairing_code:
        paired = daemon.request_pairing(args.pairing_code)
        print(f"[{args.node_id}] Pairing request submitted: {paired}")

    daemon.running = True
    while daemon.running:
        status = daemon.check_approval_status()
        print(f"[{args.node_id}] Current status: {status}")

        if status in [NodeState.APPROVED.value, NodeState.CONNECTED.value]:
            daemon.send_heartbeat()
            daemon.poll_and_execute_task()

        time.sleep(2.0)


if __name__ == "__main__":
    main()
