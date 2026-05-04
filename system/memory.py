import json
import os

class Memory:
    def __init__(self):
        self.file = "memory.json"

    def store(self, data):
        existing = []
        if os.path.exists(self.file):
            existing = json.load(open(self.file))

        existing.append(data)
        json.dump(existing, open(self.file, "w"))
