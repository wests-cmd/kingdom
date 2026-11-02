"""Universal AI Model Support Layer with provider abstraction and deterministic routing.

Supports:
- OpenAI-compatible APIs
- Ollama and local models
- ChatGPT / Anthropic official interfaces
- Capability negotiation (context limits, cost, tools, modality, latency)
- Deterministic fallback under resource constraints or offline states
"""
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ModelCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(pattern=r"^(openai_compatible|ollama|chatgpt|anthropic|custom)$")
    model_name: str = Field(min_length=1, max_length=200)
    modality: List[str] = Field(default_factory=lambda: ["text"], max_length=4)
    context_window: int = Field(default=8192, ge=512, le=2000000)
    supports_tools: bool = True
    supports_vision: bool = False
    supports_speech: bool = False
    cost_per_million_input: float = Field(default=0.0, ge=0.0)
    cost_per_million_output: float = Field(default=0.0, ge=0.0)
    estimated_latency_ms: int = Field(default=200, ge=1)
    is_local: bool = False
    is_available: bool = True


KNOWN_MODELS: Dict[str, ModelCapability] = {
    "chatgpt-4o": ModelCapability(
        provider="chatgpt",
        model_name="chatgpt-4o",
        modality=["text", "vision"],
        context_window=128000,
        supports_tools=True,
        supports_vision=True,
        cost_per_million_input=5.0,
        cost_per_million_output=15.0,
        estimated_latency_ms=800,
        is_local=False,
        is_available=True
    ),
    "ollama-llama3": ModelCapability(
        provider="ollama",
        model_name="llama3.1:8b",
        modality=["text"],
        context_window=131072,
        supports_tools=True,
        supports_vision=False,
        cost_per_million_input=0.0,
        cost_per_million_output=0.0,
        estimated_latency_ms=150,
        is_local=True,
        is_available=True
    ),
    "ollama-qwen-coder": ModelCapability(
        provider="ollama",
        model_name="qwen2.5-coder:7b",
        modality=["text"],
        context_window=32768,
        supports_tools=True,
        supports_vision=False,
        cost_per_million_input=0.0,
        cost_per_million_output=0.0,
        estimated_latency_ms=180,
        is_local=True,
        is_available=True
    ),
    "openai-gpt-4o-mini": ModelCapability(
        provider="openai_compatible",
        model_name="gpt-4o-mini",
        modality=["text", "vision"],
        context_window=128000,
        supports_tools=True,
        supports_vision=True,
        cost_per_million_input=0.15,
        cost_per_million_output=0.60,
        estimated_latency_ms=350,
        is_local=False,
        is_available=True
    )
}


class ModelSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_type: str = Field(pattern=r"^(coding|reasoning|vision|speech|general)$")
    requires_vision: bool = False
    requires_tools: bool = False
    max_budget_usd: Optional[float] = None
    prefer_local: bool = False
    allow_cloud: bool = True


class UniversalModelLayer:
    def __init__(self, models: Optional[Dict[str, ModelCapability]] = None):
        self.models = dict(KNOWN_MODELS if models is None else models)

    def register_model(self, model_id: str, cap: ModelCapability):
        self.models[model_id] = cap

    def discover_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": model_id, **cap.model_dump()}
            for model_id, cap in self.models.items()
        ]

    def select_model(self, request: ModelSelectionRequest) -> Dict[str, Any]:
        """Deterministic model selection based on constraints, cost limits, and locality."""
        candidates = []
        for model_id, cap in self.models.items():
            if not cap.is_available:
                continue
            if not request.allow_cloud and not cap.is_local:
                continue
            if request.requires_vision and not cap.supports_vision:
                continue
            if request.requires_tools and not cap.supports_tools:
                continue
            if request.max_budget_usd is not None and cap.cost_per_million_input > request.max_budget_usd * 1000:
                continue

            # Score candidates: local preference, latency, task alignment
            score = 100
            if request.prefer_local and cap.is_local:
                score += 50
            if not request.prefer_local and cap.provider == "chatgpt":
                score += 40  # Preferred primary reasoning provider
            if request.task_type == "coding" and "coder" in cap.model_name.lower():
                score += 30
            # Higher latency penalizes score
            score -= min(30, int(cap.estimated_latency_ms / 50))
            candidates.append((score, model_id, cap))

        if not candidates:
            # Local preference can rank eligible models, but cannot remove
            # required capabilities or repopulate an empty observed inventory.
            raise RuntimeError("No suitable model available matching request constraints")

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_id, best_cap = candidates[0]
        return {
            "selected_model": best_id,
            "score": best_score,
            "details": best_cap.model_dump(),
            "reason": f"Selected for {request.task_type} (score {best_score})"
        }
