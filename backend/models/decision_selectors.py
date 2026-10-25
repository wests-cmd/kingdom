"""Small learned selectors. Eligibility and execution authority stay outside models.

Artifacts imitate a synthetic resource policy, not measured task quality. The
default is shadow mode until real job outcomes justify promotion.
"""
import json
import math
from pathlib import Path

FEATURES = ('fit', 'local', 'idle', 'memory_headroom', 'success', 'latency', 'load')
ARTIFACTS = Path(__file__).parent / 'decision_artifacts'


def features(candidate):
    result = []
    for name in FEATURES:
        value = candidate.get(name, 0)
        if isinstance(value, bool):
            value = int(value)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Decision features must be finite numbers')
        result.append(max(0., min(1., float(value))))
    return result


def rank(kind, candidates, artifact_dir=None):
    """Rank already eligible candidates; never infer eligibility from a score."""
    if kind not in {'model', 'knight'} or len(candidates) > 256:
        raise ValueError('Unsupported selector or too many candidates')
    artifact = json.loads(((artifact_dir or ARTIFACTS) / (kind + '.json')).read_text(encoding='utf-8'))
    weights = artifact['weights']
    if artifact.get('schema') != 1 or artifact.get('features') != list(FEATURES) or len(weights) != len(FEATURES):
        raise ValueError('Incompatible decision artifact')
    if any(not isinstance(w, (int, float)) or not math.isfinite(w) for w in weights):
        raise ValueError('Invalid decision weights')
    identifiers = [c['id'] for c in candidates]
    if any(not isinstance(i, str) or not i for i in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError('Candidate identities must be unique')
    scored = [(sum(w*x for w, x in zip(weights, features(c))), c['id']) for c in candidates]
    return [ident for _, ident in sorted(scored, key=lambda row: (-row[0], row[1]))]


def status():
    """Public evidence contains no task text, endpoints or credentials."""
    import hashlib
    receipt = json.loads((ARTIFACTS / 'training-receipt.json').read_text(encoding='utf-8'))
    verified = all(hashlib.sha256(json.dumps(json.loads((ARTIFACTS / (kind+'.json')).read_text(encoding='utf-8')),
                   sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest() ==
                   receipt['models'][kind]['sha256'] for kind in ('model', 'knight'))
    return {'mode': 'shadow', 'artifact_hashes_verified': verified, 'training': receipt,
            'automatic_training': False, 'automatic_container_creation': False,
            'production_autonomy_proven': False}


def shadow_models(profiles, task_types=()):
    try:
        return {'mode': 'shadow', 'ranking': recommend_models(profiles, task_types),
                'affects_execution': False, 'basis': 'synthetic resource-policy imitation'}
    except (OSError, ValueError, KeyError, TypeError):
        return {'mode': 'unavailable', 'ranking': [], 'affects_execution': False}


def recommend_models(profiles, task_types=(), artifact_dir=None):
    """Caller supplies live installation-confirmed, requirement-filtered profiles.

    Configured task labels express owner preferences, not demonstrated quality.
    Missing measurements remain neutral instead of inventing fast/accurate scores.
    """
    candidates = []
    requested = set(task_types)
    for profile in profiles:
        labels = profile.get('decision_task_types', [])
        if not isinstance(labels, list):
            labels = []
        candidates.append({'id': profile['id'], 'fit': bool(requested.intersection(str(x) for x in labels)),
                           'local': profile.get('hosting') == 'local', 'idle': 0, 'memory_headroom': 0,
                           'success': 0, 'latency': 0, 'load': 0})
    return rank('model', candidates, artifact_dir)


def recommend_knights(eligible_candidates, *, independent_tasks, owner_parallel_limit,
                     artifact_dir=None):
    """Count cannot exceed independent ready tasks, owner limit or eligible nodes.

    Containers must already exist and have independently reserved host capacity.
    This function neither creates workers nor grants capabilities.
    """
    for value in (independent_tasks, owner_parallel_limit):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 256:
            raise ValueError('Parallel limits must be integers between zero and 256')
    ordered = rank('knight', eligible_candidates, artifact_dir)
    count = min(len(ordered), independent_tasks, owner_parallel_limit)
    return {'knights': ordered[:count], 'count': count, 'mode': 'shadow',
            'basis': 'synthetic resource-policy imitation; no execution authorization'}
