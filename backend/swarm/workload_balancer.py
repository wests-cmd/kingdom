class WorkloadBalancer:

    def __init__(self):
        self.knights = [
            "planner",
            "coder",
            "researcher",
            "security"
        ]

    def select_knight(self, task):

        task = str(task).lower()

        if "code" in task:
            return "coder"

        if "security" in task:
            return "security"

        if "research" in task:
            return "researcher"

        return "planner"
