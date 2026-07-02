"""Anthropic provider connector — discovers all models the API key has access to."""
from __future__ import annotations

import httpx

from providers.base import BaseConnector, ModelInfo
from utils.console import print_warning

# ── Comprehensive pricing catalog (per 1M tokens, USD) ───────────────────────
_CATALOG: dict[str, dict] = {
    # ── Claude 4.x family ────────────────────────────────────────────────────
    "claude-opus-4-6": dict(
        display_name="Claude Opus 4.6", tier="large", context_window=200_000,
        cost_per_1m_input=15.00, cost_per_1m_output=75.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "claude-sonnet-4-6": dict(
        display_name="Claude Sonnet 4.6", tier="balanced", context_window=200_000,
        cost_per_1m_input=3.00, cost_per_1m_output=15.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "claude-haiku-4-5-20251001": dict(
        display_name="Claude Haiku 4.5", tier="small", context_window=200_000,
        cost_per_1m_input=0.25, cost_per_1m_output=1.25,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "claude-haiku-4-5": dict(
        display_name="Claude Haiku 4.5", tier="small", context_window=200_000,
        cost_per_1m_input=0.25, cost_per_1m_output=1.25,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    # ── Claude 3.7 family ────────────────────────────────────────────────────
    "claude-3-7-sonnet-20250219": dict(
        display_name="Claude 3.7 Sonnet", tier="balanced", context_window=200_000,
        cost_per_1m_input=3.00, cost_per_1m_output=15.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    # ── Claude 3.5 family ────────────────────────────────────────────────────
    "claude-3-5-sonnet-20241022": dict(
        display_name="Claude 3.5 Sonnet (Oct 2024)", tier="balanced", context_window=200_000,
        cost_per_1m_input=3.00, cost_per_1m_output=15.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "claude-3-5-sonnet-20240620": dict(
        display_name="Claude 3.5 Sonnet (Jun 2024)", tier="balanced", context_window=200_000,
        cost_per_1m_input=3.00, cost_per_1m_output=15.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "claude-3-5-haiku-20241022": dict(
        display_name="Claude 3.5 Haiku", tier="small", context_window=200_000,
        cost_per_1m_input=0.80, cost_per_1m_output=4.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    # ── Claude 3 family ──────────────────────────────────────────────────────
    "claude-3-opus-20240229": dict(
        display_name="Claude 3 Opus", tier="large", context_window=200_000,
        cost_per_1m_input=15.00, cost_per_1m_output=75.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "claude-3-sonnet-20240229": dict(
        display_name="Claude 3 Sonnet", tier="balanced", context_window=200_000,
        cost_per_1m_input=3.00, cost_per_1m_output=15.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "claude-3-haiku-20240307": dict(
        display_name="Claude 3 Haiku", tier="small", context_window=200_000,
        cost_per_1m_input=0.25, cost_per_1m_output=1.25,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    # ── Claude 2 family ──────────────────────────────────────────────────────
    "claude-2.1": dict(
        display_name="Claude 2.1", tier="balanced", context_window=200_000,
        cost_per_1m_input=8.00, cost_per_1m_output=24.00,
        supports_json=True, supports_tools=False, supports_vision=False,
    ),
    "claude-2.0": dict(
        display_name="Claude 2.0", tier="balanced", context_window=100_000,
        cost_per_1m_input=8.00, cost_per_1m_output=24.00,
        supports_json=True, supports_tools=False, supports_vision=False,
    ),
    # ── Instant / Legacy ─────────────────────────────────────────────────────
    "claude-instant-1.2": dict(
        display_name="Claude Instant 1.2", tier="small", context_window=100_000,
        cost_per_1m_input=0.80, cost_per_1m_output=2.40,
        supports_json=True, supports_tools=False, supports_vision=False,
    ),
}

_FALLBACK_MODELS: list[dict] = [
    {**_CATALOG["claude-haiku-4-5"],  "external_model_id": "claude-haiku-4-5"},
    {**_CATALOG["claude-sonnet-4-6"], "external_model_id": "claude-sonnet-4-6"},
    {**_CATALOG["claude-opus-4-6"],   "external_model_id": "claude-opus-4-6"},
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
        """Fetch all models from the Anthropic API and classify each one."""
        try:
            resp = httpx.get(
                f"{self._BASE_URL}/models",
                headers=self._headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Anthropic returns {"data": [...], "has_more": bool, ...}
                api_models = data.get("data", [])
                results = self._classify_models(api_models)
                if results:
                    return results
        except Exception:
            pass
        # Discovery failed or returned nothing usable. Fall back to the built-in
        # catalog, but say so: a silent fallback hides drift from the user.
        print_warning(
            "Anthropic model discovery failed or was unavailable; using a built-in "
            "fallback catalog. The model list and pricing may be out of date."
        )
        return [ModelInfo(**m) for m in _FALLBACK_MODELS]

    def whoami(self) -> dict:
        # Anthropic has no /me endpoint
        return {"display_name": "Anthropic account", "email": None, "plan": None}

    # ── Internal ─────────────────────────────────────────────────────────────

    def _classify_models(self, api_models: list[dict]) -> list[ModelInfo]:
        results: list[ModelInfo] = []
        for m in api_models:
            model_id: str = m.get("id", "")
            if not model_id or not model_id.startswith("claude"):
                continue
            info = _info_for_id(model_id)
            if info:
                results.append(info)
        results.sort(key=lambda x: (x.cost_per_1m_input, x.external_model_id))
        return results

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _info_for_id(model_id: str) -> ModelInfo | None:
    if model_id in _CATALOG:
        return ModelInfo(external_model_id=model_id, **_CATALOG[model_id])

    # Prefix match for versioned aliases
    best_key = ""
    for key in _CATALOG:
        if model_id.startswith(key) and len(key) > len(best_key):
            best_key = key
    if best_key:
        entry = dict(_CATALOG[best_key])
        suffix = model_id[len(best_key):].lstrip("-")
        if suffix:
            entry["display_name"] = entry["display_name"] + f" ({suffix})"
        return ModelInfo(external_model_id=model_id, **entry)

    # Heuristic fallback
    mid = model_id.lower()
    if "opus" in mid:
        tier, inp, out = "large", 15.00, 75.00
    elif "sonnet" in mid:
        tier, inp, out = "balanced", 3.00, 15.00
    elif "haiku" in mid or "instant" in mid:
        tier, inp, out = "small", 0.25, 1.25
    else:
        tier, inp, out = "balanced", 3.00, 15.00

    return ModelInfo(
        external_model_id=model_id,
        display_name=model_id,
        tier=tier,
        context_window=200_000,
        cost_per_1m_input=inp,
        cost_per_1m_output=out,
        supports_json=True,
        supports_tools=True,
        supports_vision="3" in mid or "4" in mid,
    )
