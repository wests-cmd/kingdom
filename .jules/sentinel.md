## 2025-02-23 - Robust Prompt Inspection Type Safety
**Vulnerability:** Calling `lowered = content.lower()` in `InjectionDetector` raised an unhandled `AttributeError` when non-string or `None` values were supplied, leading to runtime unhandled exceptions.
**Learning:** Security firewalls must defensively handle non-string inputs before invoking string manipulation methods.
**Prevention:** Always check for `None` and convert non-string types prior to inspection in prompt firewalls.
