# Kingdom v25.5 - Intelligence Layer

class IntelligenceLayer:
    def __init__(self, config):
        self.config = config

    def route_task(self, task, hardware, knights):
        """
        Decides:
        - local vs cloud
        - small vs medium vs large model
        - swarm required or not
        """

        complexity = self.analyze(task)

        if complexity < 0.3:
            return {
                "mode": "local",
                "model_size": "small",
                "use_swarm": False
            }

        if complexity < 0.7:
            return {
                "mode": "mixed",
                "model_size": "medium",
                "use_swarm": True
            }

        return {
            "mode": "cloud",
            "model_size": "large",
            "use_swarm": True
        }

    def analyze(self, task):
        text = str(task).lower()

        score = 0
        keywords = ["analyze", "trade", "optimize", "plan", "forecast"]

        for k in keywords:
            if k in text:
                score += 0.2

        return min(score, 1.0)
