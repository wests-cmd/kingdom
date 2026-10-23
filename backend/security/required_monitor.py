"""Optional externally attested monitoring gate; not an OS isolation boundary.

A separately protected supervisor must persist the event before signing. This client
never supplies a private key or treats its own audit log as an external receipt.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
import secrets
import socket
import sys
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PROTOCOL = 'kingdom.monitor.v1'
MAX_RECEIPT_BYTES = 4096


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


@dataclass(frozen=True)
class MonitorRequirement:
    socket_path: str | None = None
    public_key_hex: str | None = None

    @property
    def required(self):
        # Partial configuration must fail closed, never silently disable the gate.
        return self.socket_path is not None or self.public_key_hex is not None

    @classmethod
    def from_environment(cls):
        return cls(os.environ.get('KINGDOM_REQUIRED_MONITOR_SOCKET'),
                   os.environ.get('KINGDOM_REQUIRED_MONITOR_PUBLIC_KEY'))


class RequiredMonitor:
    def __init__(self, requirement=None):
        # Loaded once by the trusted runtime, never from task/model parameters.
        self.requirement = requirement if requirement is not None else MonitorRequirement.from_environment()

    @staticmethod
    def verify_receipt(response, request, public_key_hex, now):
        receipt = response['receipt']
        if receipt != {**request, 'decision': 'recorded'}:
            raise PermissionError('Monitor receipt does not match the exact request')
        expiry = receipt['expires_at']
        if type(expiry) not in (int, float) or not math.isfinite(expiry) or now >= expiry or expiry - now > 5:
            raise PermissionError('Monitor receipt is stale or has excessive validity')
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(
            bytes.fromhex(response['signature']), canonical(receipt))
        return hashlib.sha256(canonical(receipt)).hexdigest()

    def attest(self, *, actor, capability, operation, parameters):
        config = self.requirement
        if not config.required:
            return None
        if sys.platform != 'linux' or not config.socket_path or not config.public_key_hex:
            raise PermissionError('Required security monitor configuration is unavailable')
        # No prompts, command arguments, credentials or filenames cross this socket.
        digest = hashlib.sha256(canonical({'actor': actor, 'capability': capability,
                                          'operation': operation, 'parameters': parameters or {}})).hexdigest()
        now = time.time()
        request = {'protocol': PROTOCOL, 'nonce': secrets.token_hex(32),
                   'operation_digest': digest, 'expires_at': now + 5}
        deadline = time.monotonic() + 0.75
        def remaining_timeout():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Monitor response exceeded deadline')
            return min(0.5, remaining)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(remaining_timeout())
                connection.connect(config.socket_path)
                connection.settimeout(remaining_timeout())
                connection.sendall(canonical(request) + b'\n')
                raw = bytearray()
                while not raw.endswith(b'\n'):
                    connection.settimeout(remaining_timeout())
                    chunk = connection.recv(min(1024, MAX_RECEIPT_BYTES + 1 - len(raw)))
                    if not chunk:
                        raise ValueError('Truncated monitor response')
                    raw.extend(chunk)
                    if len(raw) > MAX_RECEIPT_BYTES:
                        raise ValueError('Monitor response too large')
                response = json.loads(raw)
                return self.verify_receipt(response, request, config.public_key_hex, time.time())
        except Exception as exc:
            raise PermissionError('Required security monitor did not attest this operation') from exc
