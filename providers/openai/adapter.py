"""OpenAI provider adapter – wraps Chat Completions API."""
from __future__ import annotations

import time

from openai import OpenAI

from providers.base import BaseAdapter, GenerateResult


class OpenAIAdapter(BaseAdapter):
    provider_name = "openai"

    def generate(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> GenerateResult:
        client = OpenAI(api_key=api_key)
        t0 = time.monotonic()

        kwargs: dict = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }
        # o1 series does not support temperature or max_tokens param name
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
            provider="openai",
        )
