"""Anthropic provider connector (PAT-based)."""
from __future__ import annotations

import httpx

from providers.base import BaseConnector, ModelInfo

# Known Anthropic models with pricing (as of mid-2025)
# Pricing: https://www.anthropic.com/pricing
_KNOWN_MODELS: list[dict] = [
    {
        "external_model_id": "claude-haiku-4-5-20251001",
        "display_name": "Claude Haiku 4.5",
        "tier": "small",
        "context_window": 200_000,
        "cost_per_1m_input": 0.25,
        "cost_per_1m_output": 1.25,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    {
        "external_model_id": "claude-sonnet-4-6",
        "display_name": "Claude Sonnet 4.6",
        "tier": "balanced",
        "context_window": 200_000,
        "cost_per_1m_input": 3.00,
        "cost_per_1m_output": 15.00,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    {
        "external_model_id": "claude-opus-4-6",
        "display_name": "Claude Opus 4.6",
        "tier": "large",
        "context_window": 200_000,
        "cost_per_1m_input": 15.00,
        "cost_per_1m_output": 75.00,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": True,
    },
]


class AnthropicConnector(BaseConnector):
    provider_name = "anthropic"
    _BASE_URL = "https://api.anthropic.com/v1"

    def validate_key(self) -> bool:
        try:
            resp = httpx.get(
                f"{self._BASE_URL}/models",
                headers=self._headers(),
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(**m) for m in _KNOWN_MODELS]

    def whoami(self) -> dict:
        # Anthropic API has no /me endpoint; return stub
        return {"display_name": "Anthropic account", "email": None, "plan": None}

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
