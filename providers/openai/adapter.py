"""OpenAI provider adapter – wraps Chat Completions API."""
from __future__ import annotations

import time
from typing import Any

from openai import OpenAI

from providers.base import AgentTurnResult, BaseAdapter, GenerateResult, ToolCallPart


class OpenAIAdapter(BaseAdapter):
    provider_name = "openai"
    _CHAT_BASE_URL: str | None = None

    def _client(self, api_key: str) -> OpenAI:
        if self._CHAT_BASE_URL:
            return OpenAI(api_key=api_key, base_url=self._CHAT_BASE_URL)
        return OpenAI(api_key=api_key)

    def generate(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> GenerateResult:
        client = self._client(api_key)
        t0 = time.monotonic()

        kwargs: dict = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }
        if not model_id.startswith("o1"):
            kwargs["temperature"] = temperature
            kwargs["max_tokens"] = max_tokens

        completion = client.chat.completions.create(**kwargs)
        latency_ms = int((time.monotonic() - t0) * 1000)

        response_text = completion.choices[0].message.content or ""
        usage = completion.usage

        return GenerateResult(
            response_text=response_text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
            model_id=model_id,
            provider=self.provider_name,
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
        client = self._client(api_key)
        t0 = time.monotonic()
        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        if not model_id.startswith("o1"):
            kwargs["temperature"] = temperature
            kwargs["max_tokens"] = max_tokens
        completion = client.chat.completions.create(**kwargs)
        latency_ms = int((time.monotonic() - t0) * 1000)
        msg = completion.choices[0].message
        finish = completion.choices[0].finish_reason
        tool_calls: list[ToolCallPart] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    ToolCallPart(
                        id=tc.id,
                        name=tc.function.name,
                        arguments_json=tc.function.arguments or "{}",
                    )
                )
        usage = completion.usage
        return AgentTurnResult(
            text=msg.content or "",
            tool_calls=tool_calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
            model_id=model_id,
            provider=self.provider_name,
            finish_reason=str(finish) if finish else None,
        )
