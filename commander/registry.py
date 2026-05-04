class Registry:
    def __init__(self):
        self.knights = []

    def register(self, knight):
        self.knights.append(knight)

    def all(self):
        return self.knights
