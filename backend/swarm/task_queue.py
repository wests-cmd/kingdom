class TaskQueue:

    def __init__(self):
        self.tasks = []

    def add(self, task):
        self.tasks.append(task)

    def next(self):
        if not self.tasks:
            return None

        return self.tasks.pop(0)
