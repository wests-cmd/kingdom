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

    async def generate(self, prompt, model=None, provider=None, profile=None, images=None):
        if not profile and not model and not provider:
            from backend.models.profiles import ModelProfiles
            from backend.storage.db import db
            if ModelProfiles(db).list():
                profile = 'auto'
        if profile:
            return await self._generate_profile(prompt, profile, images or [])
        from backend.runtime.attachments import compact_text
        prompt = compact_text(prompt, budget=24000)['text']
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

    async def _generate_profile(self, prompt, ident, images):
        from backend.models.profiles import ModelProfiles
        from backend.storage.db import db
        from backend.models.capacity import capacity
        profiles = ModelProfiles(db)
        configured = profiles.list()
        if ident == 'auto':
            from backend.models.selection import eligible_profiles
            candidates = await eligible_profiles([profiles.get(p['id'], credential=True) for p in configured],
                                                 characters=len(prompt), images=bool(images))
        elif ident.startswith('pool:'):
            group = ident.removeprefix('pool:')
            if not group:
                raise ValueError('Select a named model pool')
            candidates = [p for p in configured if p.get('pool_group') == group and (not images or p.get('vision'))]
        else:
            candidate = profiles.get(ident)
            if images and not candidate.get('vision'):
                raise ValueError('Select a vision-capable model profile to inspect image contents')
            candidates = [candidate]
        async with capacity.acquire(candidates, server_profiles=configured) as selected:
            profile = profiles.get(selected['id'], credential=True)
            result = await self._generate_connection(prompt, profile, images)
            if ident == 'auto':
                from backend.models.selection import selection_reason
                result['selection'] = selection_reason(profile)
            return result

    async def _generate_connection(self, prompt, profile, images):
        from backend.runtime.attachments import compact_text
        from backend.models.profiles import model_tls_context
        import base64
        ident = profile['id']
        if images and not profile.get('vision'):
            raise ValueError('Select a vision-capable model profile to inspect image contents')
        limit = min(400000, max(4000, profile.get('context_characters', 24000)))
        context = compact_text(prompt, budget=limit)
        headers = {'Authorization': 'Bearer ' + profile['api_key']} if profile['api_key'] else {}
        if profile['provider'] == 'ollama':
            body = {'model': profile['model'], 'prompt': context['text'], 'stream': False}
            if profile.get('ollama_think') is not None:
                body['think'] = profile['ollama_think']
            options = {}
            if 'num_ctx' in profile: options['num_ctx'] = profile['num_ctx']
            if 'max_output_tokens' in profile: options['num_predict'] = profile['max_output_tokens']
            if options: body['options'] = options
            if images: body['images'] = [base64.b64encode(data).decode() for data in images]
            path = '/api/generate'
        else:
            content = context['text'] if not images else [{'type': 'text', 'text': context['text']}] + [
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(data).decode()}} for data in images]
            body = {'model': profile['model'], 'messages': [{'role': 'user', 'content': content}], 'stream': False}
            if 'max_output_tokens' in profile: body['max_tokens'] = profile['max_output_tokens']
            path = '/chat/completions'
        async with httpx.AsyncClient(timeout=profile.get('timeout_seconds', 120), follow_redirects=False, verify=model_tls_context(profile)) as client:
            response = await client.post(profile['endpoint'] + path, headers=headers, json=body)
            response.raise_for_status(); payload = response.json()
        if profile['provider'] == 'ollama':
            if payload.get('done') is False or payload.get('done_reason') == 'length':
                raise RuntimeError('Configured model returned an incomplete response; review the output budget')
            text = payload.get('response')
            usage = {'prompt_tokens': payload.get('prompt_eval_count', 0),
                     'completion_tokens': payload.get('eval_count', 0)}
            usage['total_tokens'] = usage['prompt_tokens'] + usage['completion_tokens']
        else:
            choice = payload['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise RuntimeError('Configured model returned an incomplete response; review the output budget')
            text, usage = choice['message']['content'], payload.get('usage', {})
        if not isinstance(text, str) or not text.strip(): raise RuntimeError('Configured model returned no text')
        result = ModelResult(profile['provider'], profile['model'], text, usage)
        self._record(result.usage)
        return {**result.export(), 'profile': ident, 'context': {k:v for k,v in context.items() if k != 'text'}}

    async def plan_chat(self, prompt, profile='auto'):
        """Plan through chat connections; coding models are not planner fallbacks."""
        payload = await self.chat(profile, {'messages': [
            {'role': 'system', 'content': 'You are Kingdom’s planning assistant. Identify uncertainty, ask a specific question when needed, and reconsider the answer before proposing work. Never execute or grant authority.'},
            {'role': 'user', 'content': prompt}]}, planner=True)
        choice = payload['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise RuntimeError('Planner response was incomplete')
        return {'text': choice['message']['content'], 'profile': payload['kingdom_profile']}

    async def chat(self, ident, request, *, planner=False):
        """Forward a complete chat/tool conversation to one owner-approved computer."""
        from backend.models.profiles import ModelProfiles
        from backend.models.profiles import model_tls_context
        from backend.models.capacity import capacity
        from backend.storage.db import db
        profiles = ModelProfiles(db)
        configured = profiles.list()
        has_images = any(isinstance(m.get('content'), list) and any(
            isinstance(part, dict) and part.get('type') in {'image_url', 'input_image', 'image'}
            for part in m['content']) for m in request['messages'])
        automatic = not ident or ident == 'auto'
        if automatic:
            import json
            from backend.models.selection import eligible_profiles
            candidates = await eligible_profiles([profiles.get(p['id'], credential=True) for p in configured],
                characters=len(json.dumps(request['messages'])), images=has_images, tools=bool(request.get('tools')))
            if not candidates:
                from backend.models.selection import ModelSelectionError
                raise ModelSelectionError('No reachable eligible model connection fits this request. Check tool support, installed models, model host connectivity and context limits in coding setup.')
        elif ident.startswith('pool:'):
            group = ident.removeprefix('pool:')
            candidates = [p for p in configured if group and p.get('pool_group') == group and (not has_images or p.get('vision'))]
        else:
            candidates = [profiles.get(ident)]
            if has_images and not candidates[0].get('vision'):
                raise ValueError('Select a vision-capable model connection for images')
        if planner:
            candidates = [p for p in candidates if 'codex' not in str(p.get('model', '')).casefold()
                          and 'codex' not in p['id'].casefold()]
            if not candidates:
                raise ValueError('Configure a non-Codex chat model for planning')
        async with capacity.acquire(candidates, server_profiles=configured) as selected:
            profile = profiles.get(selected['id'], credential=True)
            import json
            if planner and ('codex' in profile['model'].casefold() or 'codex' in profile['id'].casefold()):
                raise ValueError('Planner model changed; select a non-Codex chat connection')
            if len(json.dumps(request['messages'])) > profile.get('context_characters', 24000):
                raise ValueError('Conversation exceeds this model connection context budget')
            body = {key: value for key, value in request.items()
                    if key in {'messages', 'tools', 'tool_choice', 'temperature', 'top_p', 'reasoning_effort', 'parallel_tool_calls', 'response_format'}}
            body.update(model=profile['model'], stream=False,
                        max_tokens=min(request.get('max_tokens') or request.get('max_completion_tokens') or profile.get('max_output_tokens', 2048),
                                       profile.get('max_output_tokens', 2048)))
            if profile['provider'] == 'ollama':
                from backend.models.ollama_chat import request_body
                body = request_body(profile, request, body['max_tokens'])
                path = '/api/chat'
            else:
                path = '/chat/completions'
            headers = {'Authorization': 'Bearer ' + profile['api_key']} if profile['api_key'] else {}
            async with httpx.AsyncClient(timeout=profile.get('timeout_seconds', 120), follow_redirects=False, verify=model_tls_context(profile)) as client:
                response = await client.post(profile['endpoint'] + path, json=body, headers=headers)
                response.raise_for_status()
                payload = response.json()
            if profile['provider'] == 'ollama':
                from backend.models.ollama_chat import response_payload
                payload = response_payload(profile, payload, request)
            if not payload.get('choices'):
                raise RuntimeError('Configured model returned no chat choices')
            payload['kingdom_profile'] = profile['id']
            if automatic:
                from backend.models.selection import selection_reason
                payload['kingdom_selection'] = selection_reason(profile)
            self._record(payload.get('usage') or {})
            return payload

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
