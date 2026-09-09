# Kingdom Extension Developer Guide

## Creating an Extension

1. Import `KingdomExtensionSDK` from `sdk/kingdom_extension_sdk.py`.
2. Define `ExtensionConfig` declaring `extension_id`, `version`, `required_capabilities`, and `required_permissions`.
3. Register tool handlers using `sdk.register_tool_handler(tool_id, handler_func)`.
4. Subscribe to authorized events using `sdk.subscribe_event(event_type, handler_func)`.
