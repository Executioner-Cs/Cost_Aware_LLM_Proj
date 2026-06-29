"""OpenAI-compatible HTTP source helpers (httpx).

Talks to any OpenAI-compatible server (``/models`` + ``/chat/completions``) at a
custom base URL with an optional API key. httpx-based; no provider SDK required.
The base URL should include the API version path the server expects (for example
``http://localhost:8000/v1``). Driven via ModelSource.
"""
from __future__ import annotations

import time

import httpx

from providers.base import GenerateResult, ModelInfo

_TIMEOUT = 60.0


def _headers(api_key: str | None) -> dict:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def list_models(base_url: str, api_key: str | None = None) -> list[ModelInfo]:
    """Discover models from ``GET {base_url}/models``."""
    resp = httpx.get(f"{base_url.rstrip('/')}/models", headers=_headers(api_key), timeout=_TIMEOUT)
    resp.raise_for_status()
    models: list[ModelInfo] = []
    for entry in resp.json().get("data", []):
        model_id = entry.get("id")
        if not model_id:
            continue
        models.append(ModelInfo(
            external_model_id=model_id,
            display_name=model_id,
            tier="balanced",
            context_window=int(entry.get("context_window", 8192) or 8192),
            cost_per_1m_input=0.0,   # unknown for arbitrary endpoints
            cost_per_1m_output=0.0,
            supports_json=True,
            supports_tools=False,
            supports_vision=False,
        ))
    return models


def generate(
    base_url: str,
    prompt: str,
    model_id: str,
    api_key: str | None = None,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    **_: object,
) -> GenerateResult:
    """Run a single chat completion via ``POST {base_url}/chat/completions``."""
    t0 = time.monotonic()
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=_headers(api_key),
        json={
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage") or {}
    choices = data.get("choices") or [{}]
    return GenerateResult(
        response_text=(choices[0].get("message") or {}).get("content", ""),
        input_tokens=int(usage.get("prompt_tokens", 0) or 0),
        output_tokens=int(usage.get("completion_tokens", 0) or 0),
        latency_ms=int((time.monotonic() - t0) * 1000),
        model_id=model_id,
        provider="openai_compatible",
    )
