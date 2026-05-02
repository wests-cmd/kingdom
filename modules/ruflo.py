class ModelRegistry:
    def __init__(self):
        self.models = {}

    def register(self, name, info):
        self.models[name] = info

    def list_models(self):
        return self.models
