"""
Abstract base classes for provider connectors and adapters.
Every provider must implement these interfaces.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelInfo:
    """Normalised model descriptor returned by connector.list_models()."""
    external_model_id: str
    display_name: str
    tier: str                        # 'small' | 'balanced' | 'large'
    context_window: int
    cost_per_1m_input: float
    cost_per_1m_output: float
    supports_json: bool = False
    supports_tools: bool = False
    supports_vision: bool = False


@dataclass
class GenerateResult:
    """Result returned by adapter.generate()."""
    response_text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model_id: str
    provider: str


class BaseConnector(ABC):
    """
    Responsible for authenticating with a provider and discovering available models.
    Instantiated with a raw (decrypted) API key.
    """

    provider_name: str = ""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abstractmethod
    def validate_key(self) -> bool:
        """Return True if the API key is accepted by the provider."""

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Return normalized list of models available under this key."""

    @abstractmethod
    def whoami(self) -> dict:
        """Return dict with at least 'display_name' and optionally 'email', 'plan'."""


class BaseAdapter(ABC):
    """
    Responsible for calling a specific provider model and returning a GenerateResult.
    Stateless – takes key + model_id at call time.
    """

    provider_name: str = ""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> GenerateResult:
        """Call the provider and return a GenerateResult."""
