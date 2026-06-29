"""Ollama model source helpers (local runtime over httpx).

Local-first: talks to a running Ollama daemon at a base URL. No API key and no
heavy dependencies (httpx is a base dependency). Driven via ModelSource.
"""
from __future__ import annotations

import time

import httpx

from providers.base import GenerateResult, ModelInfo

_TIMEOUT = 60.0
DEFAULT_BASE_URL = "http://localhost:11434"


def list_models(base_url: str) -> list[ModelInfo]:
    """Discover local models from ``GET {base_url}/api/tags``."""
    resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=_TIMEOUT)
    resp.raise_for_status()
    models: list[ModelInfo] = []
    for entry in resp.json().get("models", []):
        name = entry.get("name") or entry.get("model")
        if not name:
            continue
        details = entry.get("details") or {}
        models.append(ModelInfo(
            external_model_id=name,
            display_name=name,
            tier="balanced",
            context_window=int(details.get("context_length", 8192) or 8192),
            cost_per_1m_input=0.0,   # local runtime: no per-token cost
            cost_per_1m_output=0.0,
            supports_json=True,      # Ollama supports a JSON response format
            supports_tools=False,    # tool support varies by model; conservative default
            supports_vision=False,
        ))
    return models


def generate(
    base_url: str,
    prompt: str,
    model_id: str,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    **_: object,
) -> GenerateResult:
    """Run a single chat completion via ``POST {base_url}/api/chat``."""
    t0 = time.monotonic()
    resp = httpx.post(
        f"{base_url.rstrip('/')}/api/chat",
        json={
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return GenerateResult(
        response_text=(data.get("message") or {}).get("content", ""),
        input_tokens=int(data.get("prompt_eval_count", 0) or 0),
        output_tokens=int(data.get("eval_count", 0) or 0),
        latency_ms=int((time.monotonic() - t0) * 1000),
        model_id=model_id,
        provider="ollama",
    )
