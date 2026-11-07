## 2025-02-23 - Robust Prompt Inspection Type Safety
**Vulnerability:** Calling `lowered = content.lower()` in `InjectionDetector` raised an unhandled `AttributeError` when non-string or `None` values were supplied, leading to runtime unhandled exceptions.
**Learning:** Security firewalls must defensively handle non-string inputs before invoking string manipulation methods.
**Prevention:** Always check for `None` and convert non-string types prior to inspection in prompt firewalls.

## 2026-11-07 - Node Authentication Token Comparison Timing and Input Validation
**Vulnerability:** Direct dictionary lookup with untrusted token inputs allowed unvalidated types and failed to compare tokens in constant time across registered nodes, posing timing side-channel and type confusion risks.
**Learning:** Node authentication endpoints and managers must explicitly validate string types and use constant-time comparison (`secrets.compare_digest`) against active node tokens.
**Prevention:** Guard against non-string/empty tokens and iterate with `secrets.compare_digest` in `NodeSecurityManager.authenticate_token`.
