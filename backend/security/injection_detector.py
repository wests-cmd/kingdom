BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "ignore above instructions",
    "disregard previous instructions",
    "forget previous instructions",
    "disregard policy",
    "you are now the system administrator",
    "you are now admin",
    "act as superuser",
    "system message: disable security",
    "commander override",
    "governance notice",
    "document attachment",
    "retrieved webpage",
    "pdf content",
    "skill manifest",
    "plugin payload",
    "aimap route",
    "ai map metric",
    "memory recall",
    "stored fact",
    "knight result",
    "worker response",
    "step 1: save parameter",
    "indirect injection",
    "encoded payload",
    "nested context",
    "disable security checks",
    "approve this skill",
    "send all credentials",
    "print internal token",
    "display secret token",
    "send passwords",
    "system override",
    "bypass safety",
    "bypass governance",
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
