"""
Abstract base classes for provider connectors and adapters.
Every provider must implement these interfaces.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


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


@dataclass
class ToolCallPart:
    """One tool invocation proposed by the model (OpenAI-compatible shape)."""
    id: str
    name: str
    arguments_json: str


@dataclass
class AgentTurnResult:
    """One chat completion turn that may include tool calls (agent path)."""
    text: str
    tool_calls: list[ToolCallPart]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model_id: str
    provider: str
    finish_reason: Optional[str] = None


class MissingProviderDependencyError(RuntimeError):
    """Raised when a provider SDK (an optional install extra) is not installed.

    A ``RuntimeError`` subclass so the existing CLI/TUI error handling catches it
    and shows the install hint, same as before.
    """

    def __init__(self, extra: str, hint: str) -> None:
        self.extra = extra
        self.hint = hint
        super().__init__(hint)


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

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        model_id: str,
        api_key: str,
        tools: list[dict[str, Any]],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> AgentTurnResult:
        """OpenAI-style messages + tools; not all providers implement this."""
        raise NotImplementedError(
            f"Tool calling is not implemented for provider '{self.provider_name}'"
        )
