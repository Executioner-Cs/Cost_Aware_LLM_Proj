"""Model source abstraction.

A ModelSource is anything that can expose models and execute model calls. Today
every source is a cloud provider (OpenAI, Anthropic, Gemini, Groq); this module
wraps the existing connectors and adapters behind one source-oriented interface
so later branches can add local / OpenAI-compatible / gateway sources without
changing the routing core.

This branch adds the abstraction and wraps the current providers only. No new
source types are introduced, user-facing terminology stays provider/account
based, and account/source unification remains future work. ``list_models`` and
``generate`` delegate to the existing connector/adapter, preserving behavior.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass

from providers.base import (
    BaseAdapter,
    BaseConnector,
    GenerateResult,
    MissingProviderDependencyError,
    ModelInfo,
)

_CONNECTORS = {
    "anthropic": "providers.anthropic.connector.AnthropicConnector",
    "openai": "providers.openai.connector.OpenAIConnector",
    "groq": "providers.groq.connector.GroqConnector",
    "gemini": "providers.gemini.connector.GeminiConnector",
}
_ADAPTERS = {
    "anthropic": "providers.anthropic.adapter.AnthropicAdapter",
    "openai": "providers.openai.adapter.OpenAIAdapter",
    "groq": "providers.groq.adapter.GroqAdapter",
    "gemini": "providers.gemini.adapter.GeminiAdapter",
}
# Missing provider SDK -> install extra. Keyed by the top-level module that fails
# to import; groq reuses the OpenAI SDK, so a missing "openai" maps to it too.
_MISSING_SDK_EXTRA = {
    "openai": ("openai", 'OpenAI support requires the openai extra. Install with: pip install "orchestrator-cli[openai]".'),
    "anthropic": ("anthropic", 'Anthropic support requires the anthropic extra. Install with: pip install "orchestrator-cli[anthropic]".'),
    "google": ("gemini", 'Gemini support requires the gemini extra. Install with: pip install "orchestrator-cli[gemini]".'),
}


def _load_class(dotted: str):
    """Import ``module.Class``; translate a genuinely missing provider SDK into a
    clean install hint, and re-raise any unrelated ImportError unchanged."""
    module_path, class_name = dotted.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        mapped = _MISSING_SDK_EXTRA.get((exc.name or "").split(".")[0])
        if mapped is not None:
            extra, message = mapped
            raise MissingProviderDependencyError(extra, message) from exc
        raise
    return getattr(module, class_name)


@dataclass(frozen=True)
class ModelSource:
    """A source of models, wrapping one provider's connector and adapter.

    For now the source identity is the provider name and every source is a cloud
    provider. ``list_models`` and ``generate`` delegate to the existing
    connector/adapter so current behavior is preserved exactly.
    """

    provider_name: str
    source_type: str = "cloud"
    base_url: str | None = None

    @property
    def source_id(self) -> str:
        return self.provider_name

    def _connector(self, api_key: str) -> BaseConnector:
        return _load_class(_CONNECTORS[self.provider_name])(api_key)

    def _adapter(self) -> BaseAdapter:
        return _load_class(_ADAPTERS[self.provider_name])()

    def list_models(self, api_key: str) -> list[ModelInfo]:
        if self.source_type == "ollama":
            from providers import ollama
            return ollama.list_models(self.base_url)
        if self.source_type == "openai_compatible":
            from providers import openai_compatible
            return openai_compatible.list_models(self.base_url, api_key)
        return self._connector(api_key).list_models()

    def generate(self, prompt: str, model_id: str, api_key: str, **kwargs) -> GenerateResult:
        if self.source_type == "ollama":
            from providers import ollama
            return ollama.generate(self.base_url, prompt, model_id, **kwargs)
        if self.source_type == "openai_compatible":
            from providers import openai_compatible
            return openai_compatible.generate(self.base_url, prompt, model_id, api_key, **kwargs)
        return self._adapter().generate(prompt, model_id, api_key, **kwargs)


# Source types that are not the four built-in cloud providers. They carry a
# per-instance base_url and are built on demand rather than from the registry.
NON_CLOUD_SOURCE_TYPES = frozenset({"ollama", "openai_compatible"})

_SOURCES = {name: ModelSource(provider_name=name) for name in _ADAPTERS}


def get_model_source(provider: str, *, source_type: str = "cloud", base_url: str | None = None) -> ModelSource:
    """Resolve a ModelSource. Cloud providers come from the static registry;
    local / OpenAI-compatible sources are built per call from their ``base_url``."""
    if source_type and source_type != "cloud":
        return ModelSource(provider_name=provider, source_type=source_type, base_url=base_url)
    source = _SOURCES.get(provider)
    if source is None:
        raise ValueError(f"No model source for provider '{provider}'")
    return source


def available_sources() -> list[ModelSource]:
    """All registered model sources (one per wrapped provider, for now)."""
    return list(_SOURCES.values())
