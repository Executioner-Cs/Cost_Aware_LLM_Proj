"""
ModelSource abstraction: existing providers are wrapped as sources, and
list_models / generate delegate to the existing connector / adapter unchanged.
No new source types are introduced in this branch.
"""
from __future__ import annotations

import pytest

from providers.source import get_model_source, available_sources, ModelSource
from providers.base import GenerateResult, ModelInfo, MissingProviderDependencyError


def test_existing_providers_wrap_as_sources():
    for provider in ("openai", "anthropic", "gemini", "groq"):
        source = get_model_source(provider)
        assert isinstance(source, ModelSource)
        assert source.provider_name == provider
        assert source.source_id == provider
        assert source.source_type == "cloud"  # only cloud sources exist in this branch
    assert {s.provider_name for s in available_sources()} == {"openai", "anthropic", "gemini", "groq"}


def test_get_model_source_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_model_source("nope")


def test_generate_delegates_to_adapter(monkeypatch):
    captured = {}

    def fake_generate(self, prompt, model_id, api_key, **kwargs):
        captured.update(prompt=prompt, model_id=model_id, api_key=api_key)
        return GenerateResult(
            response_text="hi", input_tokens=1, output_tokens=1,
            latency_ms=1, model_id=model_id, provider="openai",
        )

    monkeypatch.setattr("providers.openai.adapter.OpenAIAdapter.generate", fake_generate)
    result = get_model_source("openai").generate("p", "gpt-4o-mini", "sk-x")

    assert result.response_text == "hi"
    assert captured == {"prompt": "p", "model_id": "gpt-4o-mini", "api_key": "sk-x"}


def test_list_models_delegates_to_connector(monkeypatch):
    sentinel = [ModelInfo(
        external_model_id="gpt-4o-mini", display_name="GPT-4o mini", tier="small",
        context_window=128_000, cost_per_1m_input=0.15, cost_per_1m_output=0.60,
    )]

    def fake_list(self):
        return sentinel

    monkeypatch.setattr("providers.openai.connector.OpenAIConnector.list_models", fake_list)
    assert get_model_source("openai").list_models("sk-x") == sentinel


def test_missing_provider_dependency_is_runtime_error():
    # CLI/TUI error handling catches RuntimeError; the provider-dependency error
    # must remain a RuntimeError subclass so that handling keeps working.
    assert issubclass(MissingProviderDependencyError, RuntimeError)
