class ScoringHistory:

    def __init__(self):
        self.history = []

    def add(self, item):
        self.history.append(item)

    def all(self):
        return self.history
