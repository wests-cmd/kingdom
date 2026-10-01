"""Controlled native operations and independent verification of their outcomes."""
import ast
import asyncio
import hashlib
import json
from pathlib import Path
import re

from backend.integrations.tool_engine import ToolEngine, ToolDefinition
from backend.models.service import ModelService


def _text(params):
    text = params.get("text")
    if not isinstance(text, str) or len(text.encode()) > 65536:
        raise ValueError("text must be a string of at most 65536 bytes")
    return text


def _analyze(params):
    text = _text(params)
    return {"characters": len(text), "words": len(re.findall(r"\w+", text)),
            "lines": len(text.splitlines()), "sha256": hashlib.sha256(text.encode()).hexdigest()}


def _python(params):
    source = _text(params)
    tree = ast.parse(source)
    return {"valid_python": True, "functions": sorted(n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
            "classes": sorted(n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)),
            "sha256": hashlib.sha256(source.encode()).hexdigest()}


HANDLERS = {"text.analyze@1.0.0": _analyze, "code.python.analyze@1.0.0": _python}


def native_tools():
    tools = ToolEngine()
    for key, handler in HANDLERS.items():
        tool_id, version = key.split("@")
        tools.register_tool(ToolDefinition(tool_id, version, "kingdom.native", tool_id,
            "Analyze supplied text without external side effects", {"required": ["text"]}, {},
            ["compute"], [], "LOW"))
        tools.register_handler(key, handler)
    from backend.integrations.public_apis import probe_provider
    tools.register_tool(ToolDefinition("provider.metadata", "1.0.0", "kingdom.reviewed", "metadata",
        "Read a reviewed provider's public metadata", {"required": ["provider_id"]}, {},
        ["providers.test"], [], "MEDIUM"))
    def probe(params):
        if set(params) - {"provider_id", "timeout_seconds"} or "provider_id" not in params:
            raise ValueError("Only a reviewed provider identifier is allowed")
        return probe_provider(params["provider_id"], params.get("timeout_seconds", 10))
    tools.register_handler("provider.metadata@1.0.0", probe)
    return tools


def execute_request(task, capabilities):
    if not isinstance(task, dict) or not task.get("id"):
        raise ValueError("Execution requires a structured task with an identity")
    metadata = task.get("metadata", {})
    tool = metadata.get("tool")
    if tool:
        params = metadata.get("tool_parameters", {"text": task["prompt"]})
        if not isinstance(params, dict):
            raise ValueError("tool_parameters must be an object")
        output = native_tools().execute(tool, params, list(capabilities), [])
        return {"kind": "native_tool", "tool": tool, "output": output}
    if "model.inference" not in capabilities:
        raise PermissionError("Model inference is not granted")
    model = asyncio.run(ModelService().generate(task["prompt"], metadata.get("model"), metadata.get("model_provider")))
    if not isinstance(model.get("text"), str) or not model["text"].strip():
        raise RuntimeError("Configured model returned no text")
    # This deliverable is generated text, never evidence that an external action occurred.
    directory = Path("data/results")
    directory.mkdir(parents=True, exist_ok=True)
    filename = hashlib.sha256(str(task["id"]).encode()).hexdigest() + ".json"
    target = directory / filename
    payload = json.dumps(model, sort_keys=True).encode()
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(payload)
    temporary.replace(target)
    return {"kind": "model_response", "output": model, "artifact": str(target),
            "sha256": hashlib.sha256(payload).hexdigest(), "external_actions_performed": False}


def verify_request_result(task, result, allow_local_model=True):
    """Recompute pure tool results; independently read local model deliverable bytes."""
    if not isinstance(result, dict):
        raise ValueError("Missing structured execution result")
    metadata = task.get("metadata", {})
    tool = metadata.get("tool")
    if tool:
        if tool == "provider.metadata@1.0.0":
            from backend.integrations.public_apis import validate_provider_response
            if result.get("kind") != "native_tool" or result.get("tool") != tool:
                raise ValueError("Mismatched provider execution outcome")
            output = result.get("output", {})
            expected = validate_provider_response(metadata["tool_parameters"]["provider_id"],
                output.get("body", "").encode(), output.get("content_type"))
            if expected != output.get("summary") or output.get("http_status") != 200 or output.get("tls_verified") is not True or output.get("dns_public") is not True:
                raise ValueError("Independent provider response validation failed")
            return {"state": "VERIFIED", "method": "independent_response_schema_and_hash",
                    "provider_id": expected["provider_id"], "scope": "Reviewed metadata response; no external writes"}
        handler = HANDLERS.get(tool)
        if not handler or result.get("kind") != "native_tool" or result.get("tool") != tool:
            raise ValueError("Unrecognized or mismatched execution tool")
        expected = handler(metadata.get("tool_parameters", {"text": task["prompt"]}))
        if result.get("output") != expected:
            raise ValueError("Independent verification rejected the tool result")
        return {"state": "VERIFIED", "method": "independent_recomputation", "tool": tool}
    if not allow_local_model or result.get("kind") != "model_response":
        raise ValueError("No independent verifier for this execution outcome")
    target = Path("data/results") / (hashlib.sha256(str(task["id"]).encode()).hexdigest() + ".json")
    if result.get("artifact") != str(target) or result.get("external_actions_performed") is not False:
        raise ValueError("Generated text must not claim external actions")
    payload = target.read_bytes()
    if hashlib.sha256(payload).hexdigest() != result.get("sha256") or json.loads(payload) != result.get("output"):
        raise ValueError("Generated text artifact does not match the claimed deliverable")
    return {"state": "VERIFIED", "method": "read_generated_text_artifact", "external_actions_verified": False}
