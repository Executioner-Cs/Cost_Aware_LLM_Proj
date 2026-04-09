"""Anthropic provider adapter – wraps Messages API."""
from __future__ import annotations

import json
import time
from typing import Any

import anthropic

from providers.base import AgentTurnResult, BaseAdapter, GenerateResult, ToolCallPart


def _openai_tools_to_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tools:
        if t.get("type") != "function":
            continue
        f = t["function"]
        out.append(
            {
                "name": f["name"],
                "description": f.get("description") or "",
                "input_schema": f.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )
    return out


def _openai_messages_to_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    system_chunks: list[str] = []
    anth_msgs: list[dict[str, Any]] = []
    for m in messages:
        role = m["role"]
        if role == "system":
            system_chunks.append(str(m.get("content") or ""))
            continue
        if role == "user":
            anth_msgs.append({"role": "user", "content": m.get("content") or ""})
            continue
        if role == "assistant":
            parts: list[dict[str, Any]] = []
            if m.get("content"):
                parts.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                raw_args = fn.get("arguments") or "{}"
                try:
                    inp = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    inp = {}
                parts.append(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": fn.get("name", ""),
                        "input": inp,
                    }
                )
            anth_msgs.append({"role": "assistant", "content": parts})
            continue
        if role == "tool":
            anth_msgs.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m["tool_call_id"],
                            "content": m.get("content") or "",
                        }
                    ],
                }
            )
            continue
    system = "\n".join(system_chunks) if system_chunks else None
    return system, anth_msgs


class AnthropicAdapter(BaseAdapter):
    provider_name = "anthropic"

    def generate(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> GenerateResult:
        client = anthropic.Anthropic(api_key=api_key)
        t0 = time.monotonic()
        message = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        response_text = "".join(
            block.text for block in message.content if hasattr(block, "text")
        )

        return GenerateResult(
            response_text=response_text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            latency_ms=latency_ms,
            model_id=model_id,
            provider="anthropic",
        )

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        model_id: str,
        api_key: str,
        tools: list[dict[str, Any]],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> AgentTurnResult:
        client = anthropic.Anthropic(api_key=api_key)
        system, anth_msgs = _openai_messages_to_anthropic(messages)
        anth_tools = _openai_tools_to_anthropic(tools)
        t0 = time.monotonic()
        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anth_msgs,
            "tools": anth_tools,
        }
        if system:
            kwargs["system"] = system
        message = client.messages.create(**kwargs)
        latency_ms = int((time.monotonic() - t0) * 1000)

        text_parts: list[str] = []
        tool_calls: list[ToolCallPart] = []
        for block in message.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(getattr(block, "text", "") or "")
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCallPart(
                        id=str(block.id),
                        name=str(block.name),
                        arguments_json=json.dumps(getattr(block, "input", {}) or {}),
                    )
                )

        return AgentTurnResult(
            text="".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            latency_ms=latency_ms,
            model_id=model_id,
            provider="anthropic",
            finish_reason=str(message.stop_reason)
            if message.stop_reason is not None
            else None,
        )
