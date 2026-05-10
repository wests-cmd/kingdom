class EventBus:

    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)

    def consume(self):

        if not self.events:
            return None

        return self.events.pop(0)
