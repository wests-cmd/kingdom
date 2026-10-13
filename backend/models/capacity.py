"""Process-wide inference slots, shared by requests and ModelService instances."""
import asyncio
from contextlib import asynccontextmanager
from threading import Lock
from time import monotonic


class ModelCapacity:
    def __init__(self):
        self._lock = Lock()
        self._active = {}
        self._turn = 0

    @staticmethod
    def _key(profile):
        return 'computer:' + profile['computer_id'] if profile.get('computer_id') else 'endpoint:' + profile['endpoint'].rstrip('/')

    @asynccontextmanager
    async def acquire(self, profiles, wait_seconds=30, server_profiles=None):
        if not profiles:
            raise ValueError('No eligible model connections in this pool')
        deadline = monotonic() + wait_seconds
        selected = None
        while selected is None:
            with self._lock:
                # Profiles sharing a server also share its most conservative limit.
                limits = {}
                for profile in server_profiles or profiles:
                    key = self._key(profile)
                    limits[key] = min(limits.get(key, 4), profile.get('max_parallel', 1))
                choices = []
                for offset in range(len(profiles)):
                    profile = profiles[(self._turn + offset) % len(profiles)]
                    key = self._key(profile)
                    active = self._active.get(key, 0)
                    if active < limits[key]:
                        choices.append((active / limits[key], offset, profile))
                if choices:
                    selected = min(choices, key=lambda item: item[:2])[2]
                    key = self._key(selected)
                    self._active[key] = self._active.get(key, 0) + 1
                    self._turn += 1
            if selected is None:
                if monotonic() >= deadline:
                    raise TimeoutError('Model computers are busy; retry when a chat finishes')
                await asyncio.sleep(0.05)
        try:
            yield selected
        finally:
            with self._lock:
                self._active[key] -= 1
                if self._active[key] == 0:
                    del self._active[key]

    def status(self, profiles):
        with self._lock:
            limits = {}
            for profile in profiles:
                key = self._key(profile)
                limits[key] = min(limits.get(key, 4), profile.get('max_parallel', 1))
            return [{'profile': p['id'], 'pool': p.get('pool_group', ''),
                     'active': self._active.get(self._key(p), 0),
                     'max_parallel': limits[self._key(p)]} for p in profiles]


capacity = ModelCapacity()
