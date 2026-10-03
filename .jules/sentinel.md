## 2025-02-23 - Robust Prompt Inspection Type Safety
**Vulnerability:** Calling `lowered = content.lower()` in `InjectionDetector` raised an unhandled `AttributeError` when non-string or `None` values were supplied, leading to runtime unhandled exceptions.
**Learning:** Security firewalls must defensively handle non-string inputs before invoking string manipulation methods.
**Prevention:** Always check for `None` and convert non-string types prior to inspection in prompt firewalls.

## 2025-02-23 - Robust Payload Sanitization Key and Type Handling
**Vulnerability:** Calling `k.lower()` in `CredentialBroker.sanitize_payload_for_llm` raised an unhandled `AttributeError` when non-string dictionary keys (e.g. integers, HTTP status codes) were supplied, and `set()` raised `TypeError` when sanitizing sets containing unhashable elements like dicts.
**Learning:** Payload sanitizers must defensively convert dictionary keys to string before inspection and safely handle set reconstructions for complex payloads.
**Prevention:** Always stringify dict keys before checking substring patterns and catch unhashable item errors when reconstructing sets.
