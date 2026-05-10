CACHE = {}

class CacheRouter:

    def get(self, key):
        return CACHE.get(key)

    def set(self, key, value):
        CACHE[key] = value
