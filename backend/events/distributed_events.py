class DistributedEvents:

    def broadcast(self, event):

        return {
            "broadcasted": True,
            "event": event
        }
