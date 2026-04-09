"""Groq provider adapter — OpenAI-compatible Chat Completions."""
from __future__ import annotations

import time

from openai import OpenAI

from providers.base import BaseAdapter, GenerateResult

_GROQ_BASE = "https://api.groq.com/openai/v1"


class GroqAdapter(BaseAdapter):
    provider_name = "groq"

    def generate(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> GenerateResult:
        client = OpenAI(api_key=api_key, base_url=_GROQ_BASE)
        t0 = time.monotonic()
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        response_text = completion.choices[0].message.content or ""
        usage = completion.usage
        return GenerateResult(
            response_text=response_text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
            model_id=model_id,
            provider="groq",
        )
