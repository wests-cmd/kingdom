"""Guarded migration of a legacy installation ID, preserving its signing key."""
import json
import os
from pathlib import Path
import re
from threading import RLock
from uuid import uuid4

from backend.cluster.identity import KingdomIdentity

_lock = RLock()


def migrate_identity(database, expected_id, new_id=None, path='data/identities/kingdom_identity.json'):
    new_id = new_id or 'KG-' + uuid4().hex
    if not re.fullmatch(r'KG-[A-Za-z0-9_-]{1,80}', new_id) or new_id == expected_id:
        raise ValueError('Choose a distinct Kingdom identity beginning KG-')
    with _lock, database.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        identity = KingdomIdentity.load_from_file(path)
        if identity is None or identity.node_id != expected_id:
            raise ValueError('The current identity changed; review it before migration')
        # No remote references can be rewritten safely without both owners.
        if conn.execute('SELECT 1 FROM knights WHERE COALESCE(is_local,0)=0 LIMIT 1').fetchone():
            raise ValueError('Remove all remote node registrations through owner controls before migration; paired identities cannot be silently renamed')
        if conn.execute("SELECT 1 FROM tasks WHERE lower(status) NOT IN ('completed','failed','cancelled','succeeded') LIMIT 1").fetchone():
            raise ValueError('Finish or cancel active tasks before identity migration')
        source = Path(path)
        original = source.read_bytes()
        backup = source.with_name(source.name + '.migration-' + uuid4().hex + '.bak')
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(original)
        candidate = json.loads(original)
        candidate['node_id'] = new_id
        temporary = source.with_name(source.name + '.migration-' + uuid4().hex + '.tmp')
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(candidate, handle, indent=2)
            verified = KingdomIdentity.load_from_file(str(temporary))
            if verified.fingerprint != identity.fingerprint:
                raise ValueError('Signing key changed unexpectedly')
            conn.execute('UPDATE knights SET kingdom_id=? WHERE is_local=1', (new_id,))
            os.replace(temporary, source)
            conn.commit()
        except Exception:
            conn.rollback()
            # Restore atomically if a file swap preceded a failed DB commit.
            if source.read_bytes() != original:
                temporary.write_bytes(original)
                os.replace(temporary, source)
            raise
        finally:
            temporary.unlink(missing_ok=True)
        return {'previous_id': expected_id, 'node_id': new_id, 'fingerprint': identity.fingerprint,
                'signing_key_preserved': True, 'backup': str(backup), 'restart_required': True}
