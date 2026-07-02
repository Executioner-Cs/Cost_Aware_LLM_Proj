from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.tests_e2e_cli_simulation.conftest import run_cli


def test_agent_run_strips_macro_block_before_loop(runner):
    # Let the real loop run, but patch internals so it completes in one turn.
    def fake_turn(_session, messages, tools, **kwargs):
        assert "Macro constraints" in messages[0]["content"]
        assert messages[1]["content"] == "Implement X"
        from providers.base import AgentTurnResult

        return AgentTurnResult(
            text="done",
            tool_calls=[],
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            model_id="m",
            provider="openai",
        )

    with patch("db.session.get_session", return_value=MagicMock()):
        with patch(
            "agent.loop.load_agent_config",
            return_value={
                "max_iterations": 1,
                "sandbox_root": ".",
                "max_file_bytes": 1_000_000,
                "allow_shell": False,
                "max_subprocess_seconds": 60,
                "blocked_shell_patterns": "",
            },
        ):
            with patch("agent.loop.Sandbox"):
                with patch("agent.loop.agent_chat_turn", side_effect=fake_turn):
                    r = run_cli(runner, ["agent", "run", "{BRPR,VENV} Implement X", "--max-iterations", "1"])

    assert r.exit_code == 0
    assert "done" in r.stdout


def test_agent_run_without_macros_passes_goal_unchanged(runner):
    def fake_turn(_session, messages, tools, **kwargs):
        assert "Macro constraints" not in messages[0]["content"]
        assert messages[1]["content"] == "Implement Y"
        from providers.base import AgentTurnResult

        return AgentTurnResult(
            text="ok",
            tool_calls=[],
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            model_id="m",
            provider="openai",
        )

    with patch("db.session.get_session", return_value=MagicMock()):
        with patch(
            "agent.loop.load_agent_config",
            return_value={
                "max_iterations": 1,
                "sandbox_root": ".",
                "max_file_bytes": 1_000_000,
                "allow_shell": False,
                "max_subprocess_seconds": 60,
                "blocked_shell_patterns": "",
            },
        ):
            with patch("agent.loop.Sandbox"):
                with patch("agent.loop.agent_chat_turn", side_effect=fake_turn):
                    r = run_cli(runner, ["agent", "run", "Implement Y", "--max-iterations", "1"])

    assert r.exit_code == 0
    assert "ok" in r.stdout


def test_agent_run_invalid_macro_syntax_fails(runner):
    # Invalid macro size CX:two should raise inside macro parser.
    # agent CLI catches exceptions and exits 1.
    with patch("db.session.get_session", return_value=MagicMock()):
        r = run_cli(runner, ["agent", "run", "{CX:two} Implement Z", "--max-iterations", "1"])

    assert r.exit_code == 1
    assert "Agent failed" in r.stdout

