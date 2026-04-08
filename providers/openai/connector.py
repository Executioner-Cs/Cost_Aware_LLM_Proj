"""OpenAI provider connector (PAT-based)."""
from __future__ import annotations

import httpx

from providers.base import BaseConnector, ModelInfo

_KNOWN_MODELS: list[dict] = [
    {
        "external_model_id": "gpt-4o-mini",
        "display_name": "GPT-4o Mini",
        "tier": "small",
        "context_window": 128_000,
        "cost_per_1m_input": 0.15,
        "cost_per_1m_output": 0.60,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    {
        "external_model_id": "gpt-4o",
        "display_name": "GPT-4o",
        "tier": "balanced",
        "context_window": 128_000,
        "cost_per_1m_input": 2.50,
        "cost_per_1m_output": 10.00,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    {
        "external_model_id": "o1",
        "display_name": "OpenAI o1",
        "tier": "large",
        "context_window": 200_000,
        "cost_per_1m_input": 15.00,
        "cost_per_1m_output": 60.00,
        "supports_json": True,
        "supports_tools": True,
        "supports_vision": False,
    },
]


class OpenAIConnector(BaseConnector):
    provider_name = "openai"
    _BASE_URL = "https://api.openai.com/v1"

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
        try:
            resp = httpx.get(
                f"{self._BASE_URL}/me",
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "display_name": data.get("name", "OpenAI account"),
                    "email": data.get("email"),
                    "plan": None,
                }
        except Exception:
            pass
        return {"display_name": "OpenAI account", "email": None, "plan": None}

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}
