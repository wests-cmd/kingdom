import httpx
import os
import json

class OllamaClient:

    def __init__(self, base_url=None):
        self.base_url = (base_url or os.getenv("KINGDOM_OLLAMA_URL", "http://localhost:11434")).rstrip("/")

    async def generate(self, model, prompt, stream=False):

        async with httpx.AsyncClient(timeout=60) as client:

            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": stream
                }
            )
            response.raise_for_status()
            return response.json()

    async def health(self):
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return {"available": True, "models": [model["name"] for model in response.json().get("models", [])]}
        except httpx.HTTPError:
            return {"available": False, "models": []}

    async def stream(self, model, prompt):
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", f"{self.base_url}/api/generate", json={"model": model, "prompt": prompt, "stream": True}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        payload = json.loads(line)
                        yield payload.get("response", "")
