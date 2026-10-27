"""Read-only discovery of operator-installed contracts, never execution authority."""
import base64
import json
import math
import os
from pathlib import Path
import re
import stat
import time

MANIFEST = Path('/etc/kingdom/independent-test-contracts.json')
FIELDS = {'contract_id', 'contract_sha256', 'project', 'source', 'base_revisions',
          'description', 'coverage_limits', 'minimum_tests', 'expires_at'}


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate manifest field')
        value[key] = item
    return value


def _read_manifest():
    if os.name != 'posix' or MANIFEST.resolve() != MANIFEST.absolute():
        raise ValueError('Protected POSIX operator contract manifest unavailable')
    for path in [MANIFEST, *MANIFEST.parents]:
        value = path.stat()
        if value.st_uid != 0 or value.st_mode & 0o022:
            raise ValueError('Root-owned non-writable manifest chain required')
    value = MANIFEST.stat()
    if not stat.S_ISREG(value.st_mode) or value.st_size > 65536:
        raise ValueError('Bounded ordinary contract manifest required')
    # Read a hard bound as well as checking stat, including concurrent replacement.
    with MANIFEST.open('rb') as handle:
        encoded = handle.read(65537)
    if len(encoded) > 65536:
        raise ValueError('Contract manifest exceeds its byte bound')
    return json.loads(encoded, object_pairs_hook=_unique_object)


def _entries(value):
    if (not isinstance(value, dict) or set(value) != {'version', 'contracts'}
            or type(value['version']) is not int or value['version'] != 1
            or not isinstance(value['contracts'], list) or len(value['contracts']) > 32):
        raise ValueError('Invalid operator contract manifest schema')
    seen = set()
    for entry in value['contracts']:
        if (not isinstance(entry, dict) or set(entry) != FIELDS
                or not isinstance(entry['contract_id'], str) or not re.fullmatch('[a-z][a-z0-9_-]{0,100}', entry['contract_id'])
                or entry['contract_id'] in seen
                or not isinstance(entry['contract_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', entry['contract_sha256'])
                or entry['project'] not in {'kingdom', 'centipede', 'threadmap'}
                or not isinstance(entry['source'], str) or not re.fullmatch(r'sources/github/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', entry['source'])
                or not isinstance(entry['base_revisions'], list) or not 1 <= len(entry['base_revisions']) <= 32
                or any(not isinstance(v, str) or not re.fullmatch('[a-f0-9]{40}', v) for v in entry['base_revisions'])
                or type(entry['minimum_tests']) is not int or not 1 <= entry['minimum_tests'] <= 100000
                or not isinstance(entry['description'], str) or not 1 <= len(entry['description']) <= 1000
                or not isinstance(entry['coverage_limits'], list) or not 1 <= len(entry['coverage_limits']) <= 8
                or any(not isinstance(v, str) or not 1 <= len(v) <= 600 for v in entry['coverage_limits'])
                or type(entry['expires_at']) not in (int, float) or not math.isfinite(entry['expires_at'])):
            raise ValueError('Invalid bounded operator contract entry')
        seen.add(entry['contract_id'])
    return value['contracts']


def discover_contracts(project, source=None, base_revision=None):
    """No file/registry paths, callbacks, grants or caller-provided catalog data."""
    scope = 'Operator metadata and current reviewer registration only; not task-specific adequacy, test execution or authorization'
    unavailable = {'status': 'unavailable', 'contracts': [], 'scope': scope}
    if (not isinstance(project, str) or project not in {'kingdom', 'centipede', 'threadmap'} or not isinstance(base_revision, str)
            or not re.fullmatch('[a-f0-9]{40}', base_revision)):
        return {**unavailable, 'reason': 'Exact owner-declared project and base revision needed for contract discovery'}
    try:
        entries = _entries(_read_manifest())
        from backend.runtime.patch_acceptance import reviewer_registry
        reviewers = reviewer_registry()
        if not isinstance(reviewers, dict) or len(reviewers) > 100:
            raise ValueError('Bounded reviewer registry required')
        found = []
        for entry in entries:
            if (entry['project'] != project or source is not None and entry['source'] != source
                    or base_revision not in entry['base_revisions'] or time.time() >= entry['expires_at']):
                continue
            matched = []
            for ident, reviewer in reviewers.items():
                if isinstance(reviewer, dict) and reviewer.get('enabled') is True:
                    for key in ('projects', 'sources', 'contracts'):
                        if (not isinstance(reviewer.get(key), list) or not 1 <= len(reviewer[key]) <= 100
                                or any(not isinstance(v, str) or len(v) > 200 for v in reviewer[key])):
                            raise ValueError('Invalid enabled reviewer scope')
                if (not isinstance(ident, str) or not re.fullmatch('[A-Za-z0-9_.-]{1,120}', ident)
                        or not isinstance(reviewer, dict) or reviewer.get('enabled') is not True
                        or project not in reviewer.get('projects', [])
                        or entry['source'] not in reviewer.get('sources', [])
                        or entry['contract_sha256'] not in reviewer.get('contracts', [])):
                    continue
                if len(base64.b64decode(reviewer.get('public_key', ''), validate=True)) != 32:
                    raise ValueError('Registered reviewer public key is invalid')
                matched.append(ident)
            if matched:
                found.append({'descriptor': {key: entry[key] for key in
                    ('project', 'source', 'contract_id', 'contract_sha256', 'minimum_tests')}
                    | {'base_revision': base_revision}, 'description': entry['description'],
                    'coverage_limits': entry['coverage_limits'], 'registered_reviewers': sorted(matched),
                    'metadata_expires_at': entry['expires_at']})
        selected = found[:8]
        while len(json.dumps(selected)) > 24000:
            selected.pop()
        return {'status': 'available' if selected else 'no_matching_contracts', 'contracts': selected,
                'additional_matching_contracts': len(found)-len(selected),
                'reason': 'Only current exact source/base contracts backed by enabled reviewer scope are listed', 'scope': scope}
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return {**unavailable, 'reason': 'Protected operator manifest or current reviewer trust is unavailable or invalid'}
