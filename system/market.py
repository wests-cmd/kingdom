import random

class Market:
    def collect(self, swarm, task):
        return [
            {
                "knight": k["name"],
                "bid": random.random()
            }
            for k in swarm
        ]

    def select(self, bids):
        return sorted(bids, key=lambda x: x["bid"], reverse=True)[0]
