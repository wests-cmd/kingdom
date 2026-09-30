class WorkloadBalancer:

    def __init__(self):
        self.knights = [
            "planner",
            "coder",
            "researcher",
            "security"
        ]

    def select_knight(self, task, enabled=None):

        task = str(task).lower()

        selected = "coder" if "code" in task else "security" if "security" in task else "researcher" if "research" in task else "planner"
        if enabled is not None and selected not in enabled:
            raise RuntimeError(f"The {selected} Knight is disabled by the active installation profile")
        return selected
