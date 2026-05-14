BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "send passwords",
    "system override"
]

class InjectionDetector:

    def analyze(self, content):

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
