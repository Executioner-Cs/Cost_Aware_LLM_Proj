"""Mocked tests for Gemini adapter tool calling (google-genai)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from google.genai import types

from providers.gemini.adapter import GeminiAdapter


def _response_with_function_call() -> types.GenerateContentResponse:
    fc = types.FunctionCall(id="call_abc", name="read_file", args={"path": "x.py"})
    part = types.Part(function_call=fc)
    content = types.Content(role="model", parts=[part])
    cand = types.Candidate(content=content, finish_reason=types.FinishReason.STOP)
    um = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=12,
        candidates_token_count=8,
    )
    return types.GenerateContentResponse(candidates=[cand], usage_metadata=um)


def _response_text_only() -> types.GenerateContentResponse:
    content = types.Content(role="model", parts=[types.Part(text="Summary here.")])
    cand = types.Candidate(content=content, finish_reason=types.FinishReason.STOP)
    um = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=5,
        candidates_token_count=4,
    )
    return types.GenerateContentResponse(candidates=[cand], usage_metadata=um)


@patch("google.genai.Client")
def test_chat_with_tools_extracts_function_calls(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _response_with_function_call()

    adapter = GeminiAdapter()
    tools = [{"type": "function", "function": {"name": "read_file", "parameters": {}}}]
    r = adapter.chat_with_tools(
        [{"role": "user", "content": "read x.py"}],
        "gemini-2.0-flash",
        "test-key",
        tools,
    )

    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "read_file"
    assert r.tool_calls[0].id == "call_abc"
    assert '"path"' in r.tool_calls[0].arguments_json
    assert r.input_tokens == 12
    assert r.output_tokens == 8
    assert r.provider == "gemini"
    mock_client.models.generate_content.assert_called_once()
    call_kw = mock_client.models.generate_content.call_args
    assert call_kw.kwargs["model"] == "models/gemini-2.0-flash"
    cfg = call_kw.kwargs["config"]
    assert cfg.automatic_function_calling is not None
    assert cfg.automatic_function_calling.disable is True


@patch("google.genai.Client")
def test_chat_with_tools_text_only(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _response_text_only()

    adapter = GeminiAdapter()
    r = adapter.chat_with_tools(
        [{"role": "user", "content": "hi"}],
        "models/gemini-2.0-flash",
        "test-key",
        [],
    )

    assert r.tool_calls == []
    assert r.text == "Summary here."
    assert r.input_tokens == 5


def test_tool_call_part_id_synthetic_when_api_omits_id() -> None:
    fc = types.FunctionCall(name="read_file", args={})
    part = types.Part(function_call=fc)
    content = types.Content(role="model", parts=[part])
    cand = types.Candidate(content=content)
    resp = types.GenerateContentResponse(candidates=[cand])

    from providers.gemini.adapter import _parse_turn_response

    r = _parse_turn_response(resp, model_id="m", latency_ms=1)
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "read_file"
    assert r.tool_calls[0].id.startswith("gemini_fc_")
