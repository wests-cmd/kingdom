import httpx

class OllamaClient:

    async def generate(self, model, prompt):

        async with httpx.AsyncClient() as client:

            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
            )

            return response.json()
