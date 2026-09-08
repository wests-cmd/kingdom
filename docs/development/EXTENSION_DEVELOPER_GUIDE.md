# Kingdom Extension Developer Guide

## Overview

This guide explains how to build, test, and package an extension for Kingdom v40.2.

---

## 1. Extension Directory Structure

A standard Kingdom extension directory contains:

```text
my_custom_extension/
├── manifest.json
└── index.py
```

---

## 2. Manifest Specification (`manifest.json`)

Every extension must supply a valid `manifest.json`:

```json
{
  "extension_id": "ext_custom_weather",
  "name": "Custom Weather Extension",
  "version": "1.0.0",
  "description": "Fetches current weather information.",
  "author": "Developer Name",
  "kingdom_compatibility": ">=40.0.0",
  "capabilities": ["weather.read"],
  "permissions": ["network.http_get"],
  "subscribed_events": ["system.city_selected"],
  "tools": [
    {
      "tool_id": "tool_get_weather",
      "name": "Get Weather Forecast",
      "description": "Fetches current weather for a specified city.",
      "version": "1.0.0",
      "input_schema": {
        "required": ["city"]
      },
      "required_permissions": ["network.http_get"],
      "risk_level": "LOW"
    }
  ]
}
```

---

## 3. Registering & Executing Tools in Python

```python
from backend.extensions.registry import ExtensionRegistry
from backend.extensions.tool_registry import ExtensionToolRegistry
from backend.extensions.sandbox import ExtensionSandbox

# 1. Discover & Enable Extension
registry = ExtensionRegistry()
ext = registry.discover_extension(manifest_data)
registry.install_extension("ext_custom_weather")
registry.enable_extension("ext_custom_weather")

# 2. Register Executable Handler
tool_reg = ExtensionToolRegistry(registry)

def weather_handler(params):
    city = params["city"]
    return f"Weather in {city}: Clear, 20°C"

tool_reg.register_tool_executor("tool_get_weather", weather_handler)

# 3. Execute Tool
sandbox = ExtensionSandbox(registry)
result = sandbox.execute_in_sandbox(
    "ext_custom_weather",
    tool_reg.execute_tool,
    "tool_get_weather",
    {"city": "Paris"},
    caller_permissions=["network.http_get"]
)
print(result)  # "Weather in Paris: Clear, 20°C"
```

---

## 4. Testing Your Extension

Use Kingdom's extension test utilities (`tests/unit/test_extension_platform.py`) to test:
- Manifest schema validation
- Tool schema and caller permission checks
- Exception isolation and quarantine thresholds
- Side-by-side updates and rollbacks
