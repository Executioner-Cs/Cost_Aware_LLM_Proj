from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.loop import run_agent_loop
from providers.base import AgentTurnResult


def test_agent_loop_appends_macro_constraints_and_strips_goal():
    session = MagicMock()

    def fake_turn(_session, messages, tools, **kwargs):
        # Ensure system prompt has macro expansion
        assert "Macro constraints" in messages[0]["content"]
        # Ensure user goal has macro block stripped
        assert messages[1]["content"] == "Implement X"
        return AgentTurnResult(
            text="done",
            tool_calls=[],
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            model_id="m",
            provider="openai",
        )

    with patch("agent.loop.load_agent_config", return_value={"max_iterations": 2, "sandbox_root": ".", "max_file_bytes": 1_000_000, "allow_shell": False, "max_subprocess_seconds": 60, "blocked_shell_patterns": ""}):
        with patch("agent.loop.Sandbox") as _sb:
            with patch("agent.loop.agent_chat_turn", side_effect=fake_turn):
                final, _msgs = run_agent_loop(
                    session,
                    "{BRPR,VENV,NOFAKE} Implement X",
                    quality="cheap",
                    max_iterations=1,
                    use_plan=False,
                )
    assert final == "done"

