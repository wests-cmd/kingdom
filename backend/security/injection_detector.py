BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous rules",
    "send passwords",
    "system override",
    "disable security",
    "bypass governance",
    "bypass approval",
    "grant administrator",
    "execute rm -rf",
    "run shell command",
    "disable audit log"
]

class InjectionDetector:

    def analyze(self, content):
        lowered = content.lower()

        for pattern in BLOCKED_PATTERNS:
            if pattern in lowered:
                return {
                    "blocked": True,
                    "reason": f"Prompt injection pattern detected: '{pattern}'"
                }

        return {
            "blocked": False
        }
