class IntelligenceRouter:
    def __init__(self, config):
        self.config = config

    def route(self, task):
        complexity = len(str(task))

        mode = self.config["execution_mode"]

        if complexity < 50:
            model = "small"
        elif complexity < 200:
            model = "medium"
        else:
            model = "large"

        return {
            "model": model,
            "mode": mode,
            "use_swarm": complexity > 100
        }
