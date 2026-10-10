## 2025-02-23 - Robust Prompt Inspection Type Safety
**Vulnerability:** Calling `lowered = content.lower()` in `InjectionDetector` raised an unhandled `AttributeError` when non-string or `None` values were supplied, leading to runtime unhandled exceptions.
**Learning:** Security firewalls must defensively handle non-string inputs before invoking string manipulation methods.
**Prevention:** Always check for `None` and convert non-string types prior to inspection in prompt firewalls.

## 2025-02-23 - Audit Log Sanitization of Non-String Keys and Iterables
**Vulnerability:** Audit log sanitization `_sanitize_dict` called `.lower()` on dictionary keys without converting to string first, causing an `AttributeError` on non-string keys, and did not recurse into iterables (lists, tuples, sets), causing secret tokens inside iterable metadata structures to be written to disk unredacted.
**Learning:** Data sanitizers and audit loggers must handle non-string keys defensively with `str(key)` and recursively process all iterable container types.
**Prevention:** Ensure dictionary key string conversion `str(key).lower()` and handle `(list, tuple, set)` recursive element sanitization in log scrubbers.
