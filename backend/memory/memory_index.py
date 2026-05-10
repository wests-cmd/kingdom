class MemoryIndex:

    def __init__(self):
        self.index = {}

    def add(self, key, value):
        self.index[key] = value

    def get(self, key):
        return self.index.get(key)
