"""Anthropic provider adapter – wraps Messages API."""
from __future__ import annotations

import time

import anthropic

from providers.base import BaseAdapter, GenerateResult


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
