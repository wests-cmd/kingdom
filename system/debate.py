import random

class Debate:
    def generate(self, task, swarm):
        return [
            {"knight": k["name"], "score": random.random()}
            for k in swarm
        ]

    def select(self, plans):
        return sorted(plans, key=lambda x: x["score"], reverse=True)[0]
