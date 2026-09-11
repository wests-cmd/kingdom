# Kingdom Step 18 + 19 Test Strategy

## Verification Layers
1. **Unit Tests**: Manifest validation, provider registry, credential broker, tool engine, skill installer, and extension SDK.
2. **Adversarial Security Tests**: Prompt injection, credential theft, unauthorized tool calls, revoked execution (`tests/test_ecosystem_security.py`).
3. **Failure Scenarios**: Provider unauthenticated calls, missing parameters, invalid operations (`tests/test_integration_failure_scenarios.py`).
4. **Full Suite Execution**: Executing `python3 -m unittest` and `npm --prefix frontend run build`.
