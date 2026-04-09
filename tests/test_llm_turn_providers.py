"""Agent LLM turn considers all connected providers' models (tool-ready subset)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from core import llm_turn
from db.models import ModelRegistry
from providers.base import AgentTurnResult, ToolCallPart


def _model(
    pid: str,
    provider: str,
    *,
    cost_in: float = 1.0,
    cost_out: float = 1.0,
    tools: int = 1,
    ctx: int = 128_000,
) -> ModelRegistry:
    return ModelRegistry(
        id=pid,
        account_id=f"acc-{provider}",
        provider=provider,
        external_model_id=f"m-{provider}",
        display_name=None,
        tier="small",
        context_window=ctx,
        cost_per_1m_input=cost_in,
        cost_per_1m_output=cost_out,
        supports_json=1,
        supports_tools=tools,
        supports_vision=0,
        enabled=1,
        discovered_at="2026-01-01T00:00:00Z",
    )


def test_agent_chat_turn_picks_cheapest_among_multiple_providers():
    """All tool-ready providers compete; cheapest combined input+output rate wins."""
    cheap_groq = _model("1", "groq", cost_in=0.05, cost_out=0.08)
    pricey_openai = _model("2", "openai", cost_in=1.0, cost_out=2.0)
    anthropic = _model("3", "anthropic", cost_in=0.5, cost_out=0.5)
    cheap_gemini = _model("4", "gemini", cost_in=0.01, cost_out=0.01)

    mock_session = MagicMock()
    mock_account = MagicMock()
    mock_account.encrypted_token = b"enc"

    fake_turn = AgentTurnResult(
        text="ok",
        tool_calls=[],
        input_tokens=1,
        output_tokens=1,
        latency_ms=1,
        model_id="m-gemini",
        provider="gemini",
    )

    with patch("core.llm_turn.list_enabled", return_value=[pricey_openai, anthropic, cheap_groq, cheap_gemini]):
        with patch("core.llm_turn.get_account", return_value=mock_account):
            with patch("core.llm_turn.decrypt", return_value="key"):
                with patch("core.llm_turn._get_adapter") as ga:
                    mock_ad = MagicMock()
                    mock_ad.chat_with_tools.return_value = fake_turn
                    ga.return_value = mock_ad
                    out = llm_turn.agent_chat_turn(
                        mock_session,
                        [{"role": "user", "content": "hi"}],
                        [],
                    )

    assert out.provider == "gemini"
    ga.return_value.chat_with_tools.assert_called_once()
    call_args = ga.return_value.chat_with_tools.call_args[0]
    assert call_args[1] == "m-gemini"


def test_agent_chat_turn_with_only_gemini_succeeds():
    """Single Gemini model with tools support runs agent turn."""
    gemini = _model("g1", "gemini", cost_in=0.001, cost_out=0.001)

    mock_session = MagicMock()
    mock_account = MagicMock()
    mock_account.encrypted_token = b"enc"

    fake_turn = AgentTurnResult(
        text="done",
        tool_calls=[],
        input_tokens=2,
        output_tokens=3,
        latency_ms=5,
        model_id="m-gemini",
        provider="gemini",
    )

    with patch("core.llm_turn.list_enabled", return_value=[gemini]):
        with patch("core.llm_turn.get_account", return_value=mock_account):
            with patch("core.llm_turn.decrypt", return_value="key"):
                with patch("core.llm_turn._get_adapter") as ga:
                    mock_ad = MagicMock()
                    mock_ad.chat_with_tools.return_value = fake_turn
                    ga.return_value = mock_ad
                    out = llm_turn.agent_chat_turn(
                        mock_session,
                        [{"role": "user", "content": "x"}],
                        [{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
                    )

    assert out.provider == "gemini"
    assert out.text == "done"
    ga.return_value.chat_with_tools.assert_called_once()
