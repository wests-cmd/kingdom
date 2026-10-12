"""Same-computer dashboard access and an optional owner-selected startup passcode."""
import hashlib
import hmac
import secrets
import threading
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from backend.security.http_auth import owner_auth, require_owner
from backend.storage.db import db
from backend.events.event_bus import event_bus

router = APIRouter(prefix='/auth/local')
attempts = {}
attempt_lock = threading.Lock()

def local_request(request: Request):
    # Both peer and Host are checked: a forwarded or DNS-rebound remote site
    # must never receive automatic owner access.
    if not request.client or request.client.host not in {'127.0.0.1', '::1'}:
        raise HTTPException(403, 'Open Kingdom on its own computer or use a device connection code')
    if request.url.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise HTTPException(403, 'Automatic access is only available on this computer')
    if request.headers.get('X-Kingdom-Request') != '1':
        raise HTTPException(403, 'Local access request header required')
    origin = request.headers.get('origin')
    if origin and origin != str(request.base_url).rstrip('/'):
        raise HTTPException(403, 'Untrusted local access origin')

def record():
    with db.get_connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS local_access (id INTEGER PRIMARY KEY CHECK(id=1), salt TEXT NOT NULL, digest TEXT NOT NULL)')
        return conn.execute('SELECT salt,digest FROM local_access WHERE id=1').fetchone()

def matches(code, row):
    if not row:
        return True
    digest = hashlib.scrypt(code.encode(), salt=bytes.fromhex(row['salt']), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(digest, row['digest'])

class Unlock(BaseModel):
    passcode: str = Field(default='', max_length=128)

class Configure(BaseModel):
    enabled: bool
    current_passcode: str = Field(default='', max_length=128)
    new_passcode: str = Field(default='', max_length=128)

@router.post('/status', dependencies=[Depends(local_request)])
def status():
    return {'passcode_enabled': bool(record())}

@router.post('/session', dependencies=[Depends(local_request)])
def session(body: Unlock, request: Request, response: Response):
    row = record()
    if row:
        key = request.client.host
        with attempt_lock:
            recent = [t for t in attempts.get(key, []) if time.monotonic()-t < 60]
            if len(recent) >= 5:
                raise HTTPException(429, 'Too many attempts. Wait a minute and try again.')
            valid = matches(body.passcode, row)
            attempts[key] = [] if valid else recent + [time.monotonic()]
        if not valid:
            raise HTTPException(401, 'Enter your Kingdom passcode')
    response.set_cookie('kingdom_session', owner_auth.token, httponly=True, samesite='strict',
                        secure=request.url.scheme == 'https', path='/')
    return {'identity': 'owner', 'passcode_enabled': bool(row)}

@router.put('/passcode', dependencies=[Depends(local_request), Depends(require_owner)])
def configure(body: Configure):
    row = record()
    if row and not matches(body.current_passcode, row):
        raise HTTPException(401, 'Your current passcode is incorrect')
    if body.enabled and len(body.new_passcode) < 6:
        raise HTTPException(422, 'Choose a passcode with at least six characters')
    with db.get_connection() as conn:
        if body.enabled:
            salt = secrets.token_bytes(16)
            digest = hashlib.scrypt(body.new_passcode.encode(), salt=salt, n=16384, r=8, p=1).hex()
            conn.execute('INSERT OR REPLACE INTO local_access VALUES (1,?,?)', (salt.hex(),digest))
        else:
            conn.execute('DELETE FROM local_access WHERE id=1')
    event_bus.publish('security.local_passcode_changed', {'enabled': body.enabled}, source='owner')
    return {'passcode_enabled': body.enabled}

@router.post('/lock', dependencies=[Depends(local_request), Depends(require_owner)])
def lock(response: Response):
    response.delete_cookie('kingdom_session', path='/')
    return {'locked': True}

