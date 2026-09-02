"""Configurable model providers; credentials stay in environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from backend.integrations.ollama.client import OllamaClient
from backend.routing.model_router import ModelRouter


@dataclass
class ModelResult:
    provider: str
    model: str
    text: str
    usage: dict

    def export(self):
        return {"provider": self.provider, "model": self.model, "text": self.text, "usage": self.usage}


class ModelService:
    def __init__(self):
        self.router = ModelRouter()
        self.ollama = OllamaClient()
        self.openai_url = os.getenv("KINGDOM_OPENAI_COMPATIBLE_URL", "").rstrip("/")
        self.openai_key = os.getenv("KINGDOM_OPENAI_COMPATIBLE_API_KEY", "")
        self.default_provider = os.getenv("KINGDOM_MODEL_PROVIDER", "disabled")
        self.fallback_model = os.getenv("KINGDOM_MODEL_FALLBACK", "")
        self.usage = {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "estimated_cost_usd": 0.0}

    async def health(self):
        ollama = await self.ollama.health()
        return {"default_provider": self.default_provider, "ollama": ollama, "openai_compatible": {"configured": bool(self.openai_url and self.openai_key)}, "usage": self.usage}

    async def generate(self, prompt, model=None, provider=None):
        provider = provider or self.default_provider
        model = model or self.router.route(prompt)
        if provider == "ollama":
            payload = await self.ollama.generate(model, prompt)
            result = ModelResult("ollama", model, payload.get("response", ""), {"prompt_tokens": payload.get("prompt_eval_count", 0), "completion_tokens": payload.get("eval_count", 0)})
        elif provider == "openai_compatible":
            result = await self._generate_openai_compatible(model, prompt)
        else:
            raise RuntimeError("No model provider is configured; set KINGDOM_MODEL_PROVIDER")
        self._record(result.usage)
        return result.export()

    async def stream(self, prompt, model=None, provider=None):
        provider = provider or self.default_provider
        model = model or self.router.route(prompt)
        if provider != "ollama":
            raise RuntimeError("Streaming currently requires the Ollama provider")
        async for token in self.ollama.stream(model, prompt):
            yield token

    async def _generate_openai_compatible(self, model, prompt):
        if not self.openai_url or not self.openai_key:
            raise RuntimeError("OpenAI-compatible provider is not configured")
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.openai_url}/chat/completions", headers=headers, json=body)
            response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage", {})
        return ModelResult("openai_compatible", model, payload["choices"][0]["message"]["content"], {"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)})

    def _record(self, usage):
        self.usage["requests"] += 1
        self.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self.usage["completion_tokens"] += usage.get("completion_tokens", 0)
