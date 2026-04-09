"""Google Gemini provider connector (API key)."""
from __future__ import annotations

import httpx

from providers.base import BaseConnector, ModelInfo

_GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_KNOWN_MODELS: list[dict] = [
    {
        "external_model_id": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "tier": "small",
        "context_window": 1_048_576,
        "cost_per_1m_input": 0.10,
        "cost_per_1m_output": 0.40,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    {
        "external_model_id": "gemini-1.5-flash",
        "display_name": "Gemini 1.5 Flash",
        "tier": "small",
        "context_window": 1_048_576,
        "cost_per_1m_input": 0.075,
        "cost_per_1m_output": 0.30,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    {
        "external_model_id": "gemini-1.5-pro",
        "display_name": "Gemini 1.5 Pro",
        "tier": "balanced",
        "context_window": 2_097_152,
        "cost_per_1m_input": 1.25,
        "cost_per_1m_output": 5.00,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": True,
    },
]


class GeminiConnector(BaseConnector):
    provider_name = "gemini"

    def validate_key(self) -> bool:
        try:
            resp = httpx.get(
                _GEMINI_MODELS_URL,
                params={"key": self.api_key, "pageSize": 1},
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(**m) for m in _KNOWN_MODELS]

    def whoami(self) -> dict:
        return {"display_name": "Google Gemini", "email": None, "plan": None}
