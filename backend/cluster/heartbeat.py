import time

class Heartbeat:

    def ping(self):
        return {
            "alive": True,
            "timestamp": time.time()
        }
