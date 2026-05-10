class BaseKnight:

    def __init__(self, name):
        self.name = name

    def execute(self, task):
        return {
            "knight": self.name,
            "task": task,
            "status": "completed"
        }
