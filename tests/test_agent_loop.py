"""Tests for agent loop (mocked LLM turns)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.loop import run_agent_loop
from providers.base import AgentTurnResult, ToolCallPart


def test_loop_finishes_when_no_tool_calls(monkeypatch):
    session = MagicMock()
    turn = AgentTurnResult(
        text="All done.",
        tool_calls=[],
        input_tokens=1,
        output_tokens=1,
        latency_ms=1,
        model_id="m",
        provider="openai",
    )
    monkeypatch.setattr("agent.loop.agent_chat_turn", lambda *a, **k: turn)
    monkeypatch.setattr("agent.loop.dispatch_tool", lambda *a, **k: {})
    monkeypatch.setattr("agent.loop.load_agent_config", lambda *a, **k: {
        "sandbox_root": ".",
        "max_iterations": 4,
        "max_file_bytes": 1024,
        "max_subprocess_seconds": 30,
        "allow_shell": False,
        "blocked_shell_patterns": [],
    })
    text, _msgs = run_agent_loop(session, "goal", use_plan=False, home=MagicMock())
    assert text == "All done."


def test_loop_runs_tool_then_finishes(monkeypatch, tmp_path):
    session = MagicMock()
    tc = ToolCallPart(id="1", name="read_file", arguments_json='{"path":"x.txt"}')
    first = AgentTurnResult(
        text="",
        tool_calls=[tc],
        input_tokens=2,
        output_tokens=2,
        latency_ms=1,
        model_id="m",
        provider="openai",
    )
    second = AgentTurnResult(
        text="Summary.",
        tool_calls=[],
        input_tokens=3,
        output_tokens=3,
        latency_ms=1,
        model_id="m",
        provider="openai",
    )
    calls = {"n": 0}

    def fake_turn(*a, **k):
        calls["n"] += 1
        return first if calls["n"] == 1 else second

    monkeypatch.setattr("agent.loop.agent_chat_turn", fake_turn)
    monkeypatch.setattr("agent.loop.dispatch_tool", lambda *a, **k: {"ok": True, "content": "hi"})
    monkeypatch.setattr("agent.loop.load_agent_config", lambda *a, **k: {
        "sandbox_root": str(tmp_path),
        "max_iterations": 4,
        "max_file_bytes": 1024,
        "max_subprocess_seconds": 30,
        "allow_shell": False,
        "blocked_shell_patterns": [],
    })
    text, msgs = run_agent_loop(session, "read x", use_plan=False, home=MagicMock())
    assert text == "Summary."
    assert any(m.get("role") == "tool" for m in msgs)
