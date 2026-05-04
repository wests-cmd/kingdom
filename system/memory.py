import json

class Memory:
    def __init__(self):
        self.file = "memory.json"

    def store(self, data):
        try:
            existing = json.load(open(self.file))
        except:
            existing = []

        existing.append(data)
        json.dump(existing, open(self.file, "w"))
