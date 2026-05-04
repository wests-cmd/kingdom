class TaskQueue:
    def __init__(self):
        self.queue = []

    def add(self, task):
        self.queue.append(task)

    def get(self):
        return self.queue.pop(0) if self.queue else None
