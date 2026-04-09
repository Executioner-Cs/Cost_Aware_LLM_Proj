"""
Main routing pipeline.
Steps follow CLAUDE.md § Full routing pipeline exactly.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from core import classifier, reasons
from core.cost_estimator import estimate_tokens, estimate_cost
from core.model_selector import select as select_model
from core.semantic_cache import SemanticCache
from core.validator import validate, ValidationError
from db.models import Trace
from db.repositories.models import list_enabled
from db.repositories.traces import create as create_trace
from embeddings.embedder import embed
from schemas.routing import RouteRequest, RouteResult
from services.init_service import get_home, load_config
from utils.crypto import decrypt
from utils.console import console, print_warning


def _get_adapter(provider: str):
    import importlib
    _MAP = {
        "anthropic": "providers.anthropic.adapter.AnthropicAdapter",
        "openai": "providers.openai.adapter.OpenAIAdapter",
        "groq": "providers.groq.adapter.GroqAdapter",
        "gemini": "providers.gemini.adapter.GeminiAdapter",
    }
    if provider not in _MAP:
        raise ValueError(f"No adapter for provider '{provider}'")
    module_path, class_name = _MAP[provider].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def route(request: RouteRequest, session: Session) -> RouteResult:
    """Execute the full routing pipeline."""
    home = get_home()
    config = load_config(home)
    cache_cfg = config.get("cache", {})
    cost_cfg = config.get("cost", {})

    # ------------------------------------------------------------------ #
    # 1. Normalize prompt
    # ------------------------------------------------------------------ #
    prompt = re.sub(r"\s+", " ", request.prompt.strip())

    # ------------------------------------------------------------------ #
    # 2. Classify task
    # ------------------------------------------------------------------ #
    task_type = request.task_type or classifier.classify(prompt)
    quality = request.quality

    # ------------------------------------------------------------------ #
    # 3. Embed prompt
    # ------------------------------------------------------------------ #
    embedding = embed(prompt)

    # ------------------------------------------------------------------ #
    # 4. Semantic cache lookup
    # ------------------------------------------------------------------ #
    cache_enabled = cache_cfg.get("enabled", True)
    cache_result = None

    if cache_enabled:
        qdrant_path = home / "qdrant"
        threshold = cache_cfg.get("similarity_threshold", 0.92)
        task_thresholds = cache_cfg.get("task_thresholds", {})
        cache = SemanticCache(
            qdrant_path=qdrant_path,
            sqlite_session=session,
            similarity_threshold=threshold,
            task_thresholds=task_thresholds,
        )
        cache_result = cache.lookup(embedding, task_type, quality)

    if cache_result:
        # Cache HIT — write trace and return immediately
        trace = _write_trace(
            session=session,
            prompt=prompt,
            task_type=task_type,
            route_reason=reasons.SEMANTIC_CACHE_HIT,
            provider=cache_result.provider,
            model_external_id=cache_result.model_id,
            cache_hit=1,
            cache_similarity=cache_result.similarity,
            input_tokens=cache_result.input_tokens,
            output_tokens=cache_result.output_tokens,
            estimated_cost_usd=0.0,
            latency_ms=0,
            status="ok",
        )
        return RouteResult(
            task_type=task_type,
            route_reason=reasons.SEMANTIC_CACHE_HIT,
            provider=cache_result.provider,
            model_id=cache_result.model_id,
            cache_hit=True,
            cache_similarity=cache_result.similarity,
            input_tokens=cache_result.input_tokens,
            output_tokens=cache_result.output_tokens,
            estimated_cost_usd=0.0,
            latency_ms=0,
            response_text=cache_result.response_text,
        )

    # ------------------------------------------------------------------ #
    # 5. Estimate input tokens
    # ------------------------------------------------------------------ #
    input_token_estimate = estimate_tokens(prompt)

    # ------------------------------------------------------------------ #
    # 6. Select optimal model
    # ------------------------------------------------------------------ #
    all_models = list_enabled(session)
    if not all_models:
        raise RuntimeError("No models in registry. Run `orchestrator connect <provider>` first.")

    selected = select_model(all_models, task_type, quality, input_token_estimate)
    if not selected:
        _write_trace(
            session=session, prompt=prompt, task_type=task_type,
            route_reason=reasons.NO_SUITABLE_MODEL, provider=None, model_external_id=None,
            cache_hit=0, cache_similarity=None, input_tokens=None, output_tokens=None,
            estimated_cost_usd=0.0, latency_ms=None, status="error",
            error_message="No suitable model found",
        )
        raise RuntimeError("No suitable model found for the given task/quality constraints.")

    # Determine route reason
    route_reason = _route_reason(task_type, quality)

    # Dry run — return without calling provider
    if request.dry_run:
        est_cost = estimate_cost(
            input_token_estimate, 256,
            selected.cost_per_1m_input or 0.0,
            selected.cost_per_1m_output or 0.0,
        )
        return RouteResult(
            task_type=task_type,
            route_reason=route_reason,
            provider=selected.provider,
            model_id=selected.external_model_id,
            cache_hit=False,
            cache_similarity=None,
            input_tokens=input_token_estimate,
            output_tokens=None,
            estimated_cost_usd=est_cost,
            latency_ms=None,
            response_text=None,
        )

    # ------------------------------------------------------------------ #
    # 7. Call provider adapter
    # ------------------------------------------------------------------ #
    from db.repositories.accounts import get_by_id as get_account

    account = get_account(session, selected.account_id) if selected.account_id else None
    if not account:
        raise RuntimeError(
            f"No account found for model {selected.external_model_id}. "
            "Run `orchestrator accounts sync` or re-connect the provider."
        )

    api_key = decrypt(account.encrypted_token)
    adapter = _get_adapter(selected.provider)

    t0 = time.monotonic()
    try:
        gen_result = adapter.generate(prompt, selected.external_model_id, api_key)
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        _write_trace(
            session=session, prompt=prompt, task_type=task_type,
            route_reason=reasons.PROVIDER_GENERATION_FAILED,
            provider=selected.provider, model_external_id=selected.external_model_id,
            cache_hit=0, cache_similarity=None,
            input_tokens=None, output_tokens=None,
            estimated_cost_usd=0.0, latency_ms=latency_ms,
            status="error", error_message=str(exc),
        )
        raise

    # ------------------------------------------------------------------ #
    # 8. Validate output
    # ------------------------------------------------------------------ #
    try:
        validate(gen_result.response_text, task_type)
    except ValidationError as exc:
        _write_trace(
            session=session, prompt=prompt, task_type=task_type,
            route_reason=reasons.VALIDATION_FAILED,
            provider=selected.provider, model_external_id=selected.external_model_id,
            cache_hit=0, cache_similarity=None,
            input_tokens=gen_result.input_tokens, output_tokens=gen_result.output_tokens,
            estimated_cost_usd=0.0, latency_ms=gen_result.latency_ms,
            status="validation_failed", error_message=str(exc),
        )
        raise

    # ------------------------------------------------------------------ #
    # 9. Store in semantic cache
    # ------------------------------------------------------------------ #
    actual_cost = estimate_cost(
        gen_result.input_tokens, gen_result.output_tokens,
        selected.cost_per_1m_input or 0.0,
        selected.cost_per_1m_output or 0.0,
    )

    if cache_enabled:
        cache.store(
            embedding=embedding,
            task_type=task_type,
            quality=quality,
            response_text=gen_result.response_text,
            provider=selected.provider,
            model_id=selected.external_model_id,
            input_tokens=gen_result.input_tokens,
            output_tokens=gen_result.output_tokens,
        )

    # Cost warning
    warn_threshold = cost_cfg.get("warn_above_usd", 0.01)
    if actual_cost > warn_threshold:
        print_warning(f"Request cost ${actual_cost:.6f} exceeds warning threshold ${warn_threshold}")

    # ------------------------------------------------------------------ #
    # 10. Write trace
    # ------------------------------------------------------------------ #
    _write_trace(
        session=session, prompt=prompt, task_type=task_type, route_reason=route_reason,
        provider=selected.provider, model_external_id=selected.external_model_id,
        cache_hit=0, cache_similarity=None,
        input_tokens=gen_result.input_tokens, output_tokens=gen_result.output_tokens,
        estimated_cost_usd=actual_cost, latency_ms=gen_result.latency_ms,
        status="ok",
    )

    return RouteResult(
        task_type=task_type,
        route_reason=route_reason,
        provider=selected.provider,
        model_id=selected.external_model_id,
        cache_hit=False,
        cache_similarity=None,
        input_tokens=gen_result.input_tokens,
        output_tokens=gen_result.output_tokens,
        estimated_cost_usd=actual_cost,
        latency_ms=gen_result.latency_ms,
        response_text=gen_result.response_text,
    )


def _route_reason(task_type: str, quality: str) -> str:
    if quality == "best":
        return reasons.BEST_QUALITY_FORCED
    if quality == "cheap":
        return reasons.CHEAP_QUALITY_FORCED
    if task_type == "reasoning":
        return reasons.REASONING_TASK_BALANCED
    if task_type == "json_extract":
        return reasons.JSON_EXTRACT_JSON_CAPABLE
    return reasons.SIMPLE_TASK_CHEAPEST


def _write_trace(
    session: Session,
    prompt: str,
    task_type: str,
    route_reason: str,
    provider: Optional[str],
    model_external_id: Optional[str],
    cache_hit: int,
    cache_similarity: Optional[float],
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    estimated_cost_usd: float,
    latency_ms: Optional[int],
    status: str,
    error_message: Optional[str] = None,
) -> Trace:
    trace = Trace(
        id=str(uuid.uuid4()),
        prompt_preview=prompt[:200],
        task_type=task_type,
        route_reason=route_reason,
        provider=provider,
        model_external_id=model_external_id,
        cache_hit=cache_hit,
        cache_similarity=cache_similarity,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return create_trace(session, trace)
