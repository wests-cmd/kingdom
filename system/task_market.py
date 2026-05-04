import random

class TaskMarket:
    def bid(self, knight):
        return {
            "knight": knight["name"],
            "score": random.random()
        }

    def choose(self, bids):
        return sorted(bids, key=lambda x: x["score"], reverse=True)[0]
