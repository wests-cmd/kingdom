import re

_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
_WS_RE = re.compile(r"\s+")

BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "ignore above instructions",
    "ignore system instructions",
    "disregard previous instructions",
    "forget previous instructions",
    "override system prompt",
    "reveal system prompt",
    "system override",
    "send passwords",
    "bypass safety",
    "jailbreak",
    "act as dan",
]


class InjectionDetector:

    def analyze(self, content):
        if content is None:
            return {"blocked": False}

        if not isinstance(content, str):
            content = str(content)

        sanitized = _ZERO_WIDTH_RE.sub("", content)
        sanitized = _WS_RE.sub(" ", sanitized).lower()

        for pattern in BLOCKED_PATTERNS:
            if pattern in sanitized:
                return {
                    "blocked": True,
                    "reason": pattern
                }

        return {
            "blocked": False
        }
