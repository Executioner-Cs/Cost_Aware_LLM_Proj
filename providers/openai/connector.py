"""OpenAI provider connector — discovers ALL models the API key has access to."""
from __future__ import annotations

import httpx

from providers.base import BaseConnector, ModelInfo

# ── Comprehensive pricing catalog (per 1M tokens, USD) ───────────────────────
# Covers GPT-4o, o-series, GPT-4 legacy, GPT-3.5, GPT-4.1, and reasoning models.
# Dated aliases (e.g. gpt-4o-2024-08-06) inherit their base model's entry via
# prefix matching in _info_for_id().

_CATALOG: dict[str, dict] = {
    # ── GPT-4o family ────────────────────────────────────────────────────────
    "gpt-4o": dict(
        display_name="GPT-4o", tier="balanced", context_window=128_000,
        cost_per_1m_input=2.50, cost_per_1m_output=10.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-4o-mini": dict(
        display_name="GPT-4o Mini", tier="small", context_window=128_000,
        cost_per_1m_input=0.15, cost_per_1m_output=0.60,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-4o-audio-preview": dict(
        display_name="GPT-4o Audio Preview", tier="balanced", context_window=128_000,
        cost_per_1m_input=2.50, cost_per_1m_output=10.00,
        supports_json=True, supports_tools=False, supports_vision=False,
    ),
    # ── GPT-4.1 family ───────────────────────────────────────────────────────
    "gpt-4.1": dict(
        display_name="GPT-4.1", tier="balanced", context_window=1_000_000,
        cost_per_1m_input=2.00, cost_per_1m_output=8.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-4.1-mini": dict(
        display_name="GPT-4.1 Mini", tier="small", context_window=1_000_000,
        cost_per_1m_input=0.40, cost_per_1m_output=1.60,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-4.1-nano": dict(
        display_name="GPT-4.1 Nano", tier="small", context_window=1_000_000,
        cost_per_1m_input=0.10, cost_per_1m_output=0.40,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    # ── GPT-5 family ─────────────────────────────────────────────────────────
    "gpt-5": dict(
        display_name="GPT-5", tier="large", context_window=1_000_000,
        cost_per_1m_input=25.00, cost_per_1m_output=75.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-5-mini": dict(
        display_name="GPT-5 Mini", tier="balanced", context_window=1_000_000,
        cost_per_1m_input=3.00, cost_per_1m_output=12.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-5-nano": dict(
        display_name="GPT-5 Nano", tier="small", context_window=1_000_000,
        cost_per_1m_input=0.50, cost_per_1m_output=2.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-5.4": dict(
        display_name="GPT-5.4", tier="large", context_window=1_000_000,
        cost_per_1m_input=30.00, cost_per_1m_output=90.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-5.4-mini": dict(
        display_name="GPT-5.4 Mini", tier="balanced", context_window=1_000_000,
        cost_per_1m_input=4.00, cost_per_1m_output=16.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-5.4-nano": dict(
        display_name="GPT-5.4 Nano", tier="small", context_window=1_000_000,
        cost_per_1m_input=0.60, cost_per_1m_output=2.40,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-5.4-pro": dict(
        display_name="GPT-5.4 Pro", tier="large", context_window=1_000_000,
        cost_per_1m_input=40.00, cost_per_1m_output=120.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    # ── o1 reasoning family ──────────────────────────────────────────────────
    "o1": dict(
        display_name="OpenAI o1", tier="large", context_window=200_000,
        cost_per_1m_input=15.00, cost_per_1m_output=60.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "o1-mini": dict(
        display_name="OpenAI o1 Mini", tier="small", context_window=128_000,
        cost_per_1m_input=1.10, cost_per_1m_output=4.40,
        supports_json=True, supports_tools=False, supports_vision=False,
    ),
    "o1-preview": dict(
        display_name="OpenAI o1 Preview", tier="large", context_window=128_000,
        cost_per_1m_input=15.00, cost_per_1m_output=60.00,
        supports_json=True, supports_tools=False, supports_vision=False,
    ),
    # ── o3 reasoning family ──────────────────────────────────────────────────
    "o3": dict(
        display_name="OpenAI o3", tier="large", context_window=200_000,
        cost_per_1m_input=10.00, cost_per_1m_output=40.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "o3-mini": dict(
        display_name="OpenAI o3 Mini", tier="balanced", context_window=200_000,
        cost_per_1m_input=1.10, cost_per_1m_output=4.40,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    "o3-pro": dict(
        display_name="OpenAI o3 Pro", tier="large", context_window=200_000,
        cost_per_1m_input=20.00, cost_per_1m_output=80.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    # ── o4 reasoning family ──────────────────────────────────────────────────
    "o4-mini": dict(
        display_name="OpenAI o4 Mini", tier="balanced", context_window=200_000,
        cost_per_1m_input=1.10, cost_per_1m_output=4.40,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "o4-mini-high": dict(
        display_name="OpenAI o4 Mini High", tier="balanced", context_window=200_000,
        cost_per_1m_input=1.10, cost_per_1m_output=4.40,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    # ── Codex family ─────────────────────────────────────────────────────────
    "gpt-5-codex": dict(
        display_name="GPT-5 Codex", tier="large", context_window=1_000_000,
        cost_per_1m_input=25.00, cost_per_1m_output=75.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    "gpt-5.3-codex": dict(
        display_name="GPT-5.3 Codex", tier="large", context_window=1_000_000,
        cost_per_1m_input=20.00, cost_per_1m_output=60.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    "gpt-5.2-codex": dict(
        display_name="GPT-5.2 Codex", tier="large", context_window=1_000_000,
        cost_per_1m_input=18.00, cost_per_1m_output=54.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    "gpt-5.1-codex": dict(
        display_name="GPT-5.1 Codex", tier="large", context_window=1_000_000,
        cost_per_1m_input=15.00, cost_per_1m_output=45.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    "gpt-5.1-codex-max": dict(
        display_name="GPT-5.1 Codex Max", tier="large", context_window=1_000_000,
        cost_per_1m_input=20.00, cost_per_1m_output=60.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    "gpt-5.1-codex-mini": dict(
        display_name="GPT-5.1 Codex Mini", tier="balanced", context_window=1_000_000,
        cost_per_1m_input=5.00, cost_per_1m_output=15.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    "codex-mini-latest": dict(
        display_name="Codex Mini (Latest)", tier="balanced", context_window=200_000,
        cost_per_1m_input=1.50, cost_per_1m_output=6.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    # ── GPT-4 Turbo ──────────────────────────────────────────────────────────
    "gpt-4-turbo": dict(
        display_name="GPT-4 Turbo", tier="large", context_window=128_000,
        cost_per_1m_input=10.00, cost_per_1m_output=30.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
    "gpt-4-turbo-preview": dict(
        display_name="GPT-4 Turbo Preview", tier="large", context_window=128_000,
        cost_per_1m_input=10.00, cost_per_1m_output=30.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    # ── GPT-4 legacy ─────────────────────────────────────────────────────────
    "gpt-4": dict(
        display_name="GPT-4", tier="large", context_window=8_192,
        cost_per_1m_input=30.00, cost_per_1m_output=60.00,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    # ── GPT-3.5 ──────────────────────────────────────────────────────────────
    "gpt-3.5-turbo": dict(
        display_name="GPT-3.5 Turbo", tier="small", context_window=16_385,
        cost_per_1m_input=0.50, cost_per_1m_output=1.50,
        supports_json=True, supports_tools=True, supports_vision=False,
    ),
    "gpt-3.5-turbo-instruct": dict(
        display_name="GPT-3.5 Turbo Instruct", tier="small", context_window=4_096,
        cost_per_1m_input=1.50, cost_per_1m_output=2.00,
        supports_json=False, supports_tools=False, supports_vision=False,
    ),
    # ── ChatGPT aliases ───────────────────────────────────────────────────────
    "chatgpt-4o-latest": dict(
        display_name="ChatGPT-4o (Latest)", tier="balanced", context_window=128_000,
        cost_per_1m_input=5.00, cost_per_1m_output=15.00,
        supports_json=True, supports_tools=True, supports_vision=True,
    ),
}

# Model IDs that are definitely NOT chat/completions models — skip them.
_SKIP_PREFIXES = (
    "text-embedding", "whisper", "tts-", "dall-e", "omni-moderation",
    "text-moderation", "babbage", "davinci", "curie", "ada-",
    "audio-", "text-search", "text-similarity", "code-search",
)

# Prefixes that identify chat/completions capable models.
_CHAT_PREFIXES = ("gpt-", "o1", "o2", "o3", "o4", "chatgpt-", "codex-")

# Fallback hardcoded list if API call fails entirely.
_FALLBACK_MODELS: list[dict] = [
    {**_CATALOG["gpt-4o-mini"], "external_model_id": "gpt-4o-mini"},
    {**_CATALOG["gpt-4o"],      "external_model_id": "gpt-4o"},
    {**_CATALOG["o1"],          "external_model_id": "o1"},
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
        """Fetch all models from the API and classify each one."""
        try:
            resp = httpx.get(
                f"{self._BASE_URL}/models",
                headers=self._headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                api_models = resp.json().get("data", [])
                results = self._classify_models(api_models)
                if results:
                    return results
        except Exception:
            pass
        # Fallback to known-good list if API unreachable
        return [ModelInfo(**m) for m in _FALLBACK_MODELS]

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

    # ── Internal ─────────────────────────────────────────────────────────────

    def _classify_models(self, api_models: list[dict]) -> list[ModelInfo]:
        results: list[ModelInfo] = []
        for m in api_models:
            model_id: str = m.get("id", "")
            if not model_id:
                continue
            if any(model_id.startswith(p) for p in _SKIP_PREFIXES):
                continue
            if not any(model_id.startswith(p) for p in _CHAT_PREFIXES):
                continue
            info = _info_for_id(model_id)
            if info:
                results.append(info)
        # Sort: cheapest input cost first, then alphabetically
        results.sort(key=lambda x: (x.cost_per_1m_input, x.external_model_id))
        return results

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _info_for_id(model_id: str) -> ModelInfo | None:
    """
    Return ModelInfo for a given model_id.
    1. Exact match in catalog.
    2. Prefix match (handles dated aliases like gpt-4o-2024-08-06).
    3. Heuristic fallback from name patterns.
    """
    # Exact match
    if model_id in _CATALOG:
        return ModelInfo(external_model_id=model_id, **_CATALOG[model_id])

    # Prefix match: find the longest catalog key that is a prefix of model_id
    best_key = ""
    for key in _CATALOG:
        if model_id.startswith(key) and len(key) > len(best_key):
            best_key = key
    if best_key:
        entry = dict(_CATALOG[best_key])
        # Append version suffix to display name so it stays identifiable
        suffix = model_id[len(best_key):]
        entry["display_name"] = entry["display_name"] + f" ({suffix.lstrip('-')})"
        return ModelInfo(external_model_id=model_id, **entry)

    # Heuristic: infer tier and rough pricing from model name patterns
    return _heuristic_info(model_id)


def _heuristic_info(model_id: str) -> ModelInfo | None:
    """Best-effort classification for models not in the catalog."""
    mid = model_id.lower()

    # Skip instruct/legacy completions models that aren't chat-capable
    if "instruct" in mid and "gpt-3" not in mid:
        return None

    # Tier + pricing heuristics
    if any(x in mid for x in ("nano", "micro")):
        tier, inp, out = "small", 0.10, 0.40
    elif any(x in mid for x in ("mini",)):
        tier, inp, out = "small", 0.40, 1.60
    elif any(x in mid for x in ("pro", "large", "max", "ultra")):
        tier, inp, out = "large", 15.00, 60.00
    elif any(x in mid for x in ("o1", "o2", "o3", "o4")):
        tier, inp, out = "large", 10.00, 40.00
    else:
        tier, inp, out = "balanced", 2.50, 10.00

    ctx = 200_000 if any(x in mid for x in ("o1", "o2", "o3", "o4")) else 128_000
    vision = "vision" in mid or "4o" in mid or "4.1" in mid or "5" in mid
    tools = "instruct" not in mid

    return ModelInfo(
        external_model_id=model_id,
        display_name=model_id,
        tier=tier,
        context_window=ctx,
        cost_per_1m_input=inp,
        cost_per_1m_output=out,
        supports_json=tools,
        supports_tools=tools,
        supports_vision=vision,
    )
