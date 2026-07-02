"""Groq provider connector (OpenAI-compatible API, PAT-based)."""
from __future__ import annotations

import httpx

from providers.base import BaseConnector, ModelInfo

_BASE = "https://api.groq.com/openai/v1"

# Curated list; Groq rotates model IDs — adjust as needed.
_KNOWN_MODELS: list[dict] = [
    {
        "external_model_id": "llama-3.3-70b-versatile",
        "display_name": "Llama 3.3 70B (Groq)",
        "tier": "balanced",
        "context_window": 128_000,
        "cost_per_1m_input": 0.59,
        "cost_per_1m_output": 0.79,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": False,
    },
    {
        "external_model_id": "llama-3.1-8b-instant",
        "display_name": "Llama 3.1 8B Instant",
        "tier": "small",
        "context_window": 131_072,
        "cost_per_1m_input": 0.05,
        "cost_per_1m_output": 0.08,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": False,
    },
    {
        "external_model_id": "mixtral-8x7b-32768",
        "display_name": "Mixtral 8x7B",
        "tier": "balanced",
        "context_window": 32_768,
        "cost_per_1m_input": 0.24,
        "cost_per_1m_output": 0.24,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": False,
    },
]


class GroqConnector(BaseConnector):
    provider_name = "groq"

    def validate_key(self) -> bool:
        try:
            resp = httpx.get(
                f"{_BASE}/models",
                headers=self._headers(),
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(**m) for m in _KNOWN_MODELS]

    def whoami(self) -> dict:
        return {"display_name": "Groq account", "email": None, "plan": None}

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}
