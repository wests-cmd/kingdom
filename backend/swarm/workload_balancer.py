class WorkloadBalancer:

    def __init__(self, registry=None):
        self.registry = registry
        self.knights = [
            "planner",
            "coder",
            "researcher",
            "memory",
            "security"
        ]

    def select_knight(self, task, required_capability: str = None) -> str:
        prompt = str(task).lower() if isinstance(task, (str, dict)) else ""

        # If task is a dict, extract prompt and capability requirements
        if isinstance(task, dict):
            prompt = str(task.get("prompt", "") or task.get("description", "")).lower()
            if not required_capability:
                required_capability = task.get("required_capability") or task.get("capability")

        # Determine target role based on capability or keyword match
        target = "planner"
        if required_capability:
            cap = required_capability.lower()
            if "code" in cap:
                target = "coder"
            elif "security" in cap or "audit" in cap:
                target = "security"
            elif "research" in cap or "search" in cap:
                target = "researcher"
            elif "memory" in cap or "storage" in cap:
                target = "memory"
        else:
            if "code" in prompt or "python" in prompt or "bug" in prompt or "function" in prompt:
                target = "coder"
            elif "security" in prompt or "auth" in prompt or "audit" in prompt or "permission" in prompt:
                target = "security"
            elif "research" in prompt or "search" in prompt or "investigate" in prompt:
                target = "researcher"
            elif "memory" in prompt or "remember" in prompt or "history" in prompt:
                target = "memory"

        # Check registry availability and active load if registry provided
        if self.registry:
            # Check if target knight exists and is ready
            knight = self.registry.get(target)
            if knight is not None:
                return target

            # Fallback to least loaded active knight
            if hasattr(self.registry, "status"):
                statuses = self.registry.status()
                if statuses:
                    sorted_knights = sorted(statuses, key=lambda s: s.get("active", 0))
                    return sorted_knights[0]["name"]

        return target
