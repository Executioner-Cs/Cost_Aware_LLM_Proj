"""
Single LLM chat turn with tools for the agent path.
Does not use semantic cache (agent steps are non-deterministic).

Model selection is **global across all connected accounts**: every enabled row
in ``model_registry`` (from Anthropic, OpenAI, Groq, Gemini, …) is eligible,
subject to tool support and ``AGENT_TOOL_PROVIDERS``. The cheapest model that
satisfies the ``tools`` task and quality tier wins; the correct account key is
resolved via that row's ``account_id``.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core.cost_estimator import estimate_tokens
from core.model_selector import select as select_model
from db.repositories.accounts import get_by_id as get_account
from db.repositories.models import list_enabled
from providers.base import AgentTurnResult
from utils.crypto import decrypt

# Providers whose adapter implements chat_with_tools end-to-end. Others are
# excluded from agent tool rounds so we never select a model that cannot run
# the unified tool schema (add a provider here when its adapter is ready).
AGENT_TOOL_PROVIDERS: frozenset[str] = frozenset(
    {"openai", "anthropic", "groq", "gemini"}
)


def _get_adapter(provider: str):
    import importlib

    _MAP = {
        "anthropic": "providers.anthropic.adapter.AnthropicAdapter",
        "openai": "providers.openai.adapter.OpenAIAdapter",
        "groq": "providers.groq.adapter.GroqAdapter",
        "gemini": "providers.gemini.adapter.GeminiAdapter",
    }
    if provider not in _MAP:
        raise ValueError(f"No adapter for provider '{provider}'")
    module_path, class_name = _MAP[provider].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def agent_chat_turn(
    session: Session,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    quality: str = "balanced",
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> AgentTurnResult:
    """
    Select the cheapest tool-capable model across **all** connected providers
    and run one ``chat_with_tools`` turn using that model's account credentials.
    """
    task_type = "tools"
    prompt_blob = "\n".join(str(m.get("content", "")) for m in messages)
    input_token_estimate = max(estimate_tokens(prompt_blob), 256)

    all_models = list_enabled(session)
    if not all_models:
        raise RuntimeError("No models in registry. Run `orchestrator connect <provider>` first.")

    tool_ready = [m for m in all_models if m.provider in AGENT_TOOL_PROVIDERS]
    if not tool_ready:
        raise RuntimeError(
            "No models from providers with agent tool support. "
            f"Supported providers: {sorted(AGENT_TOOL_PROVIDERS)}. "
            "Connect at least one of them."
        )

    selected = select_model(tool_ready, task_type, quality, input_token_estimate)
    if not selected:
        raise RuntimeError("No suitable tool-capable model found.")

    account = get_account(session, selected.account_id) if selected.account_id else None
    if not account:
        raise RuntimeError("No account found for selected model.")

    api_key = decrypt(account.encrypted_token)
    adapter = _get_adapter(selected.provider)
    return adapter.chat_with_tools(
        messages,
        selected.external_model_id,
        api_key,
        tools,
        max_tokens=max_tokens,
        temperature=temperature,
    )
