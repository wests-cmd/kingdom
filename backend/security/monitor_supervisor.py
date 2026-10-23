"""Separately runnable Linux audit/signing supervisor. No key generation.

Deployment must protect this code, config and key from the effect-producing worker.
This process attests durable recording, not semantic permission to execute an effect.
"""
import argparse
from collections import OrderedDict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import sys
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from backend.security.required_monitor import PROTOCOL, canonical

MAX_REQUEST = 512
MAX_CONFIG = 4096
MAX_AUDIT = 64 * 1024 * 1024
HEX64 = re.compile(r'[0-9a-f]{64}\Z')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not allowed')
        result[key] = value
    return result


def protect_parents(path, uid):
    """Reject writable/untrusted ancestors and symlink traversal before opening files."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise PermissionError('An absolute protected path is required')
    for directory in reversed(path.parents):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0, uid} or info.st_mode & 0o022:
            raise PermissionError('Unprotected or symlinked path ancestor')


def protected_read(path, uid, *, secret=False, limit=MAX_CONFIG):
    protect_parents(path, uid)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        allowed_owners = {uid} if secret else {0, uid}
        forbidden_mode = 0o077 if secret else 0o022
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in allowed_owners or info.st_mode & forbidden_mode or info.st_nlink != 1 or info.st_size > limit:
            raise PermissionError('Unsafe file ownership, type, size or permissions')
        data = os.read(fd, limit + 1)
        if len(data) > limit:
            raise ValueError('Protected file exceeds size limit')
        return data
    finally:
        os.close(fd)


def load_configuration(path):
    uid = os.geteuid()
    data = json.loads(protected_read(path, uid), object_pairs_hook=unique_object)
    if set(data) != {'allowed_peer_uid', 'socket_path', 'key_path', 'audit_path'}:
        raise ValueError('Exact supervisor configuration fields required')
    peer = data['allowed_peer_uid']
    if type(peer) is not int or peer <= 0 or peer == uid:
        raise PermissionError('Allowed worker UID must be explicit, non-root and distinct from supervisor')
    for name in ('socket_path', 'key_path', 'audit_path'):
        if not isinstance(data[name], str):
            raise ValueError('Paths must be strings')
        protect_parents(data[name], uid)
    socket_directory = Path(data['socket_path']).parent.lstat()
    if socket_directory.st_uid != uid or socket_directory.st_mode & 0o022:
        raise PermissionError('Supervisor must exclusively own its socket directory')
    audit_directory = Path(data['audit_path']).parent.lstat()
    if audit_directory.st_uid != uid or audit_directory.st_mode & 0o077:
        raise PermissionError('Audit directory must be private to supervisor')
    key_bytes = protected_read(data['key_path'], uid, secret=True, limit=32)
    if len(key_bytes) != 32:
        raise ValueError('An existing raw 32-byte Ed25519 key is required')
    return data, Ed25519PrivateKey.from_private_bytes(key_bytes)


def validate_request(request, now):
    if not isinstance(request, dict) or set(request) != {'protocol', 'nonce', 'operation_digest', 'expires_at'}:
        raise ValueError('Exact request fields required')
    if request['protocol'] != PROTOCOL:
        raise ValueError('Unsupported monitor protocol')
    if not isinstance(request['nonce'], str) or not HEX64.fullmatch(request['nonce']):
        raise ValueError('Invalid nonce')
    if not isinstance(request['operation_digest'], str) or not HEX64.fullmatch(request['operation_digest']):
        raise ValueError('Invalid operation digest')
    expiry = request['expires_at']
    if type(expiry) not in (int, float) or not math.isfinite(expiry) or not 0 < expiry - now <= 5:
        raise ValueError('Expired or excessively long request')


class DurableAudit:
    def __init__(self, path):
        uid = os.geteuid()
        protect_parents(path, uid)
        self.fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        self.failed = False
        try:
            info = os.fstat(self.fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077 or info.st_nlink != 1:
                raise PermissionError('Audit file must be a private, singly linked regular file')
            if info.st_size and os.pread(self.fd, 1, info.st_size - 1) != b'\n':
                raise PermissionError('Audit has an incomplete tail; operator recovery required')
            # Persist newly created file's directory entry before acknowledging any event.
            parent = os.open(str(Path(path).parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except BaseException:
            os.close(self.fd)
            raise

    def append(self, event):
        if self.failed:
            raise OSError('Audit is unavailable after a previous write failure')
        raw = canonical(event) + b'\n'
        if len(raw) > 1024 or os.fstat(self.fd).st_size + len(raw) > MAX_AUDIT:
            raise OSError('Audit capacity exhausted; operator archival required')
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(self.fd, raw[offset:])
                if written <= 0:
                    raise OSError('Audit append failed')
                offset += written
            os.fsync(self.fd)  # MUST complete before producing any signed receipt.
        except BaseException:
            self.failed = True
            raise

    def close(self):
        os.close(self.fd)


class Supervisor:
    def __init__(self, allowed_peer_uid, signer, audit):
        if type(allowed_peer_uid) is not int or allowed_peer_uid <= 0 or allowed_peer_uid == os.geteuid():
            raise PermissionError('Worker and supervisor must be distinct OS identities')
        self.allowed_peer_uid = allowed_peer_uid
        self.signer = signer
        self.audit = audit
        self.seen = OrderedDict()

    def record_and_sign(self, request, peer_uid):
        now = time.time()
        validate_request(request, now)
        if peer_uid != self.allowed_peer_uid:
            raise PermissionError('Unapproved peer UID')
        # Serial loop; fixed-size replay window, no unbounded per-client state.
        for nonce, expiry in list(self.seen.items()):
            if expiry <= now:
                del self.seen[nonce]
        if request['nonce'] in self.seen or len(self.seen) >= 1024:
            raise PermissionError('Replayed request or nonce budget exhausted')
        receipt = {**request, 'decision': 'recorded'}
        self.audit.append({'protocol': PROTOCOL, 'event': 'recorded', 'peer_uid': peer_uid,
                           'recorded_at': now, **request})
        # Slow / failed storage must not yield a usable receipt afterwards.
        if time.time() >= request['expires_at']:
            raise PermissionError('Request expired while recording')
        self.seen[request['nonce']] = request['expires_at']
        return {'receipt': receipt, 'signature': self.signer.sign(canonical(receipt)).hex()}

    def handle_connection(self, connection):
        peer_uid = None
        raw = bytearray()
        try:
            peer_pid, peer_uid, peer_gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
            if peer_uid != self.allowed_peer_uid:
                raise PermissionError('Unapproved peer UID')
            read_request(connection, raw)
            response = self.record_and_sign(json.loads(raw, object_pairs_hook=unique_object), peer_uid)
            connection.settimeout(0.25)
            connection.sendall(canonical(response) + b'\n')
        except Exception:
            # Content-free denial evidence; log failure never creates a signature.
            try:
                self.audit.append({'protocol': PROTOCOL, 'event': 'denied', 'peer_uid': peer_uid,
                    'recorded_at': time.time(), 'input_digest': hashlib.sha256(raw).hexdigest()})
            except Exception:
                pass
            # Deliberately close without an error oracle or signed receipt.


def read_request(connection, raw):
    """Bound transport input independently from peer authorization and signing."""
    deadline = time.monotonic() + 0.5
    while not raw.endswith(b'\n'):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Input deadline exceeded')
        connection.settimeout(remaining)
        chunk = connection.recv(min(256, MAX_REQUEST + 1 - len(raw)))
        if not chunk:
            raise ValueError('Truncated request')
        raw.extend(chunk)
        if len(raw) > MAX_REQUEST:
            raise ValueError('Request too large')


def notify_watchdog():
    endpoint = os.environ.get('NOTIFY_SOCKET')
    if endpoint:
        if endpoint.startswith('@'):
            endpoint = '\0' + endpoint[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notification:
            notification.sendto(b'WATCHDOG=1', endpoint)


def serve(config_path):
    if sys.platform != 'linux' or not hasattr(socket, 'SO_PEERCRED'):
        raise RuntimeError('Linux SO_PEERCRED is required')
    config, key = load_configuration(config_path)
    audit = DurableAudit(config['audit_path'])
    supervisor = Supervisor(config['allowed_peer_uid'], key, audit)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    running = True
    def stop(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    socket_inode = None
    try:
        # Never unlink an existing path on startup; a conflict needs operator review.
        listener.bind(config['socket_path'])
        os.chmod(config['socket_path'], 0o660)
        socket_inode = os.lstat(config['socket_path']).st_ino
        listener.listen(4)
        listener.settimeout(0.5)
        while running:
            notify_watchdog()
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            with connection:
                supervisor.handle_connection(connection)
    finally:
        listener.close()
        audit.close()
        if socket_inode is not None:
            info = os.lstat(config['socket_path'])
            if stat.S_ISSOCK(info.st_mode) and info.st_ino == socket_inode:
                os.unlink(config['socket_path'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    serve(parser.parse_args().config)
