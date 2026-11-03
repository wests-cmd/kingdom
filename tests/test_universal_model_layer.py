"""Tests for the Universal AI Model Support Layer."""
import pytest
from backend.models.universal_layer import (
    UniversalModelLayer,
    ModelSelectionRequest
)
from backend.models.universal_layer import ModelCapability


@pytest.mark.parametrize('requirements', [
    {'requires_vision': True},
    {'requires_tools': True},
    {'requires_vision': True, 'requires_tools': True},
])
def test_no_fallback_can_discard_required_capabilities(requirements):
    layer = UniversalModelLayer({'text-only': ModelCapability(
        provider='ollama', model_name='installed-text-only', is_local=True,
        supports_tools=False, supports_vision=False,
    )})
    with pytest.raises(RuntimeError, match='No suitable model'):
        layer.select_model(ModelSelectionRequest(task_type='general', **requirements))


def test_explicit_empty_inventory_does_not_restore_example_models():
    layer = UniversalModelLayer({})
    assert layer.discover_models() == []
    with pytest.raises(RuntimeError, match='No suitable model'):
        layer.select_model(ModelSelectionRequest(task_type='general'))


def test_discover_models():
    layer = UniversalModelLayer()
    models = layer.discover_models()
    assert len(models) >= 4
    model_ids = [m["id"] for m in models]
    assert "chatgpt-4o" in model_ids
    assert "ollama-llama3" in model_ids
    assert "ollama-qwen-coder" in model_ids
    assert "openai-gpt-4o-mini" in model_ids


def test_select_model_coding_prefers_coder():
    layer = UniversalModelLayer()
    req = ModelSelectionRequest(task_type="coding", prefer_local=True)
    decision = layer.select_model(req)
    assert decision["selected_model"] == "ollama-qwen-coder"
    assert decision["details"]["is_local"] is True


def test_select_model_chatgpt_primary_reasoning():
    layer = UniversalModelLayer()
    req = ModelSelectionRequest(task_type="reasoning", prefer_local=False, allow_cloud=True)
    decision = layer.select_model(req)
    assert decision["selected_model"] == "chatgpt-4o"


def test_select_model_vision_requirement():
    layer = UniversalModelLayer()
    req = ModelSelectionRequest(task_type="vision", requires_vision=True)
    decision = layer.select_model(req)
    assert decision["details"]["supports_vision"] is True


def test_select_model_strict_local_only():
    layer = UniversalModelLayer()
    req = ModelSelectionRequest(task_type="general", allow_cloud=False)
    decision = layer.select_model(req)
    assert decision["details"]["is_local"] is True


def test_select_model_deterministic_fallback():
    # If no model matches a tight budget, fallback to local zero-cost model
    layer = UniversalModelLayer()
    req = ModelSelectionRequest(task_type="general", max_budget_usd=0.000000001, allow_cloud=True)
    decision = layer.select_model(req)
    assert decision["details"]["is_local"] is True
