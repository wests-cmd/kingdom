import time

class Timeline:

    def __init__(self):
        self.events = []

    def add(self, event):

        self.events.append({
            "timestamp": time.time(),
            "event": event
        })

    def all(self):
        return self.events
