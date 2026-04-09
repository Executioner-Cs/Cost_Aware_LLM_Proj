"""Mocked tests for OpenAI adapter tool calling."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from providers.base import ToolCallPart
from providers.openai.adapter import OpenAIAdapter


def test_chat_with_tools_extracts_tool_calls():
    fn = MagicMock()
    fn.name = "read_file"
    fn.arguments = '{"path":"x.py"}'
    tc = MagicMock()
    tc.id = "call_1"
    tc.function = fn
    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "tool_calls"
    usage = MagicMock()
    usage.prompt_tokens = 12
    usage.completion_tokens = 8
    comp = MagicMock()
    comp.choices = [choice]
    comp.usage = usage

    with patch.object(OpenAIAdapter, "_client") as mock_client_factory:
        mock_client_factory.return_value.chat.completions.create.return_value = comp
        adapter = OpenAIAdapter()
        tools = [{"type": "function", "function": {"name": "read_file", "parameters": {}}}]
        r = adapter.chat_with_tools(
            [{"role": "user", "content": "read x.py"}],
            "gpt-4o-mini",
            "sk-test",
            tools,
        )
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "read_file"
    assert r.input_tokens == 12
    assert r.provider == "openai"
