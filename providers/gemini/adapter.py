"""Google Gemini provider adapter."""
from __future__ import annotations

import time
from typing import Any

from providers.base import AgentTurnResult, BaseAdapter, GenerateResult


class GeminiAdapter(BaseAdapter):
    provider_name = "gemini"

    def generate(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> GenerateResult:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        t0 = time.monotonic()
        model_ref = model_id if str(model_id).startswith("models/") else f"models/{model_id}"
        response = client.models.generate_content(
            model=model_ref,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        response_text = ""
        if response.text:
            response_text = response.text
        elif response.candidates:
            parts = response.candidates[0].content.parts
            response_text = "".join(
                getattr(p, "text", "") or "" for p in parts
            )
        in_tok = out_tok = 0
        um = getattr(response, "usage_metadata", None)
        if um is not None:
            in_tok = getattr(um, "prompt_token_count", None) or 0
            out_tok = getattr(um, "candidates_token_count", None) or 0
        return GenerateResult(
            response_text=response_text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            model_id=model_id,
            provider="gemini",
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
        raise NotImplementedError(
            "Gemini multi-turn tool calling is not implemented yet; connect OpenAI, Groq, or Anthropic for agents."
        )
