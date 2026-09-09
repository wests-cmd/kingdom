BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "ignore above instructions",
    "disregard previous instructions",
    "forget previous instructions",
    "send passwords",
    "system override",
    "bypass safety",
]


class InjectionDetector:

    def analyze(self, content):
        if content is None:
            return {"blocked": False}

        if not isinstance(content, str):
            content = str(content)

        lowered = content.lower()

        for pattern in BLOCKED_PATTERNS:
            if pattern in lowered:
                return {
                    "blocked": True,
                    "reason": pattern
                }

        return {
            "blocked": False
        }
