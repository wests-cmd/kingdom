"""Automatic placement uses configured requirements and live server evidence."""
import asyncio

import httpx

class ModelSelectionError(ValueError):
    """Safe configuration diagnostic; never includes endpoint credentials."""

from backend.models.profiles import model_tls_context


async def available(profile):
    """Check installation without inference; do not infer capabilities from names."""
    headers = {'Authorization': 'Bearer ' + profile['api_key']} if profile.get('api_key') else {}
    path = '/api/tags' if profile['provider'] == 'ollama' else '/models'
    try:
        async with httpx.AsyncClient(timeout=3, follow_redirects=False, verify=model_tls_context(profile)) as client:
            response = await client.get(profile['endpoint'] + path, headers=headers)
            response.raise_for_status()
            payload = response.json()
        names = {item.get('name') or item.get('model') for item in payload.get('models', [])} if profile['provider'] == 'ollama' else {item.get('id') for item in payload.get('data', [])}
        return profile['model'] in names
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return False


async def eligible_profiles(profiles, *, characters=0, images=False, tools=False):
    candidates = [p for p in profiles if not p.get('disabled', False)
                  and (not images or p.get('vision') is True)
                  and (not tools or p.get('supports_tools') is True)
                  and characters <= p.get('context_characters', 24000)]
    # Bound total probing concurrency even for a large saved catalogue.
    semaphore = asyncio.Semaphore(4)
    async def probe(profile):
        async with semaphore:
            return await available(profile)
    ready = await asyncio.gather(*(probe(p) for p in candidates))
    return [p for p, ok in zip(candidates, ready) if ok]


def selection_reason(profile):
    return {'mode': 'auto', 'profile': profile['id'],
            'reason': 'Installed model confirmed by live server model list; configured request requirements fit; selected using available shared computer capacity.',
            'capability_basis': 'Owner-configured capabilities; no model quality or capability inferred from its name.'}
