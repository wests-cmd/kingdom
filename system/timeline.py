class Timeline:
    def __init__(self):
        self.events = []

    def record(self, task, knight):
        self.events.append({
            "task": task,
            "assigned": knight
        })

    def update(self, result):
        self.events.append({"result": result})
