"""Routing policy engine and route explanations.

A RoutingPolicy declares hard filters and a deterministic scoring formula over
the dimensions the product routes on. The default policy reproduces the existing
cheapest-capable selection exactly (the candidate pool comes from
``model_selector.candidates``, and the winner is its cheapest member), so the
default route is behavior-preserving. Explicit policies change the ranking.

Dimensions backed by data today: cost, quality (tier), context window, JSON and
tool support, and privacy (local source). ``latency`` and ``reliability`` are
part of the policy shape but score neutrally until benchmark scorecards provide
that data (a later branch); they are not invented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core import model_selector
from core.model_selector import TIER_ORDER
from db.models import ModelRegistry

# Providers that run locally (no prompt data leaves the machine).
_LOCAL_PROVIDERS = frozenset({"ollama"})


@dataclass(frozen=True)
class RoutingPolicy:
    """Hard filters plus scoring weights. The default is cheapest-capable."""

    name: str = "default"
    # Hard filters, applied on top of the task/quality/context filters the
    # candidate pool already enforces.
    require_local: bool = False   # privacy: only local sources
    require_json: bool = False
    require_tools: bool = False
    # Scoring weights (higher = stronger preference). Used by non-default policies.
    weight_cost: float = 1.0      # prefer cheaper
    weight_quality: float = 0.0   # prefer higher tier
    weight_context: float = 0.0   # prefer larger context window
    # Prefer models that scored well on the user's own benchmark task sets. The
    # score per model is supplied to ``decide`` by the caller (core stays I/O-free).
    prefer_scorecards: bool = False
    weight_scorecard: float = 0.0
    # Declared but not yet scored (no data until benchmark scorecards exist).
    weight_latency: float = 0.0
    weight_reliability: float = 0.0
    # Auto preset: derive a per-task minimum tier (quality floor) and rank the
    # models that clear it, instead of using the quality min/max tier range.
    task_aware_floor: bool = False

    @property
    def is_default(self) -> bool:
        return (
            not self.require_local and not self.require_json and not self.require_tools
            and self.weight_quality == 0.0 and self.weight_context == 0.0
            and not self.prefer_scorecards and self.weight_scorecard == 0.0
            and self.weight_latency == 0.0 and self.weight_reliability == 0.0
            and not self.task_aware_floor
        )


DEFAULT_POLICY = RoutingPolicy()

# The Auto preset: constraint-aware everyday routing. It sets a per-task quality
# floor (so it does not pick the cheapest weak model), then ranks the models that
# clear the floor by benchmark evidence with cost as the tie-breaker (so it does
# not always pick the biggest or the priciest model either). weight_quality stays
# 0: Auto prefers the cheapest model above the floor, not the highest tier.
AUTO_POLICY = RoutingPolicy(
    name="auto", task_aware_floor=True, prefer_scorecards=True,
    weight_scorecard=2.0, weight_cost=1.0,
)
_PRIVACY_POLICY = RoutingPolicy(name="privacy-first", require_local=True)
_QUALITY_POLICY = RoutingPolicy(name="quality-first", weight_quality=2.0, weight_cost=0.5)
# Benchmark-driven routing: a high score on the user's own task sets dominates,
# with cost as the tie-breaker so unscored models fall back to cheapest-capable.
_BENCHMARKED_POLICY = RoutingPolicy(
    name="benchmarked", prefer_scorecards=True, weight_scorecard=3.0, weight_cost=0.5,
)

# Named policies the engine can resolve: one object per distinct behavior, with the
# user-facing preset vocabulary aliased onto them (the same pattern the existing
# 'default'/'cheapest' synonyms already use). Aliasing rather than cloning means
# there are no duplicate policy objects to drift apart.
POLICIES: dict[str, RoutingPolicy] = {
    # cheapest-capable (the default route)
    "default": DEFAULT_POLICY,
    "cheapest": DEFAULT_POLICY,
    "cheap": DEFAULT_POLICY,
    # constraint-aware Auto (per-task quality floor)
    "auto": AUTO_POLICY,
    # 'fast' is recognized but its latency-aware ranking is not built yet (no
    # reliable per-model latency feeds scoring). It routes via Auto and the router
    # says so (PRESET_NOTES), instead of giving a misleading "unknown policy".
    "fast": AUTO_POLICY,
    # hard local-only (privacy)
    "privacy-first": _PRIVACY_POLICY,
    "private": _PRIVACY_POLICY,
    "local": _PRIVACY_POLICY,
    # quality-weighted (prefer higher tier)
    "quality-first": _QUALITY_POLICY,
    "best": _QUALITY_POLICY,
    "deep": _QUALITY_POLICY,
    # scorecard-driven
    "benchmarked": _BENCHMARKED_POLICY,
}

# Presets that are intentionally routed via another policy until their own
# behavior lands. The note is surfaced to the user so the mapping stays honest.
PRESET_NOTES: dict[str, str] = {
    "fast": "'fast' routes via Auto for now; latency-aware ranking is planned, not yet built.",
}


@dataclass
class RouteDecision:
    """The chosen model plus a human-readable account of why."""

    selected: Optional[ModelRegistry]
    reason: str
    ranked: list[tuple[str, float]]   # (external_model_id, score), best first
    fallback: list[str]               # ordered alternatives, excludes the winner
    explanation: str


def get_policy(name: Optional[str]) -> RoutingPolicy:
    """Resolve a named policy, defaulting to cheapest-capable."""
    if not name:
        return DEFAULT_POLICY
    return POLICIES.get(name, DEFAULT_POLICY)


def _cost(m: ModelRegistry) -> float:
    return (m.cost_per_1m_input or 0.0) + (m.cost_per_1m_output or 0.0)


def _passes_hard_filters(m: ModelRegistry, policy: RoutingPolicy) -> bool:
    if policy.require_local and m.provider not in _LOCAL_PROVIDERS:
        return False
    if policy.require_json and not m.supports_json:
        return False
    if policy.require_tools and not m.supports_tools:
        return False
    return True


def _score(
    m: ModelRegistry,
    policy: RoutingPolicy,
    pool: list[ModelRegistry],
    scores: Optional[dict[str, float]] = None,
) -> float:
    max_cost = max((_cost(x) for x in pool), default=0.0) or 1.0
    max_ctx = max((x.context_window or 0 for x in pool), default=0) or 1
    cost_term = policy.weight_cost * (1.0 - _cost(m) / max_cost)              # cheaper -> higher
    quality_term = policy.weight_quality * (TIER_ORDER.get(m.tier, 0) / 2.0)  # higher tier -> higher
    context_term = policy.weight_context * ((m.context_window or 0) / max_ctx)
    # Unscored models contribute 0 here, so cost still ranks them: the explicit
    # no-scorecard fallback to cheapest-capable.
    scorecard_term = 0.0
    if policy.weight_scorecard and scores:
        scorecard_term = policy.weight_scorecard * scores.get(m.external_model_id, 0.0)
    return cost_term + quality_term + context_term + scorecard_term


def _explain(
    winner: ModelRegistry,
    policy: RoutingPolicy,
    scores: Optional[dict[str, float]] = None,
) -> str:
    prefs = []
    if policy.require_local:
        prefs.append("local-only (privacy)")
    if policy.require_json:
        prefs.append("JSON-capable")
    if policy.require_tools:
        prefs.append("tool-capable")
    if policy.weight_quality:
        prefs.append("quality-weighted")
    if policy.weight_context:
        prefs.append("context-weighted")
    if policy.prefer_scorecards:
        prefs.append("scorecard-weighted")
    detail = f" under {', '.join(prefs)}" if prefs else ""
    note = ""
    if policy.prefer_scorecards:
        winner_score = (scores or {}).get(winner.external_model_id)
        if winner_score is not None:
            note = f" It scored {winner_score:.0%} on your benchmarks."
        else:
            note = " No scorecard for the winner; fell back to cheapest-capable."
    return (
        f"Policy '{policy.name}' selected {winner.external_model_id} "
        f"({winner.provider}, tier {winner.tier}){detail}.{note}"
    )


def _auto_pool(
    models: list[ModelRegistry],
    task_type: str,
    quality: str,
    input_tokens: int,
    policy: RoutingPolicy,
) -> tuple[list[ModelRegistry], str, bool]:
    """Auto's candidate pool: capable models that clear the task's quality floor,
    cheapest-first, after the policy's hard filters.

    Returns ``(pool, floor_name, floor_met)``. When no capable model reaches the
    floor, the pool falls back to the best-effort capable models (still after hard
    filters, so a local-only policy never falls back to cloud) and ``floor_met`` is
    False so the explanation can say so honestly.
    """
    floor_name = model_selector.auto_floor_tier(task_type, quality)
    floor = TIER_ORDER.get(floor_name, 0)
    capable = [
        m for m in model_selector.capable_models(models, task_type, input_tokens)
        if _passes_hard_filters(m, policy)
    ]
    clearing = [m for m in capable if TIER_ORDER.get(m.tier, 0) >= floor]
    if clearing:
        return clearing, floor_name, True
    return capable, floor_name, False


def _explain_auto(
    winner: ModelRegistry,
    policy: RoutingPolicy,
    scores: Optional[dict[str, float]],
    task_type: str,
    floor_name: str,
    floor_met: bool,
) -> str:
    local = " local-only" if policy.require_local else ""
    if floor_met:
        head = (
            f"Auto inferred a '{task_type}' task and set a '{floor_name}' quality floor, "
            f"then chose the cheapest{local} model that clears it"
        )
    else:
        head = (
            f"Auto inferred a '{task_type}' task wanting a '{floor_name}' floor, but no "
            f"available{local} model reaches it, so it used the best available"
        )
    winner_score = (scores or {}).get(winner.external_model_id)
    if winner_score is not None:
        evidence = f" It scored {winner_score:.0%} on your benchmarks."
    elif scores:
        evidence = " No benchmark score for it; ranked by cost above the floor."
    else:
        evidence = " No benchmark evidence yet; ranked by cost above the floor."
    return (
        f"{head}: {winner.external_model_id} "
        f"({winner.provider}, tier {winner.tier}).{evidence}"
    )


def decide(
    models: list[ModelRegistry],
    task_type: str,
    quality: str = "balanced",
    input_tokens: int = 0,
    policy: RoutingPolicy = DEFAULT_POLICY,
    scores: Optional[dict[str, float]] = None,
) -> RouteDecision:
    """Choose a model under *policy* and explain the choice.

    For the default policy the winner is the cheapest capable model, identical to
    ``model_selector.select``. Explicit policies score the candidate pool. The Auto
    preset (``task_aware_floor``) builds its pool from a per-task quality floor
    instead of the quality min/max tier range. ``scores`` maps ``external_model_id``
    to a benchmark score in [0, 1]; it is consulted only by scorecard-aware policies
    and supplied by the caller so this module performs no I/O.
    """
    floor_name = ""
    floor_met = True
    if policy.task_aware_floor:
        pool, floor_name, floor_met = _auto_pool(models, task_type, quality, input_tokens, policy)
    else:
        pool = [
            m for m in model_selector.candidates(models, task_type, quality, input_tokens)
            if _passes_hard_filters(m, policy)
        ]

    if not pool:
        # Auto builds its pool from the task floor and capabilities, not the quality
        # tier range, so naming 'quality' here would misdescribe why nothing matched.
        constraint = (
            f"task '{task_type}' under the '{floor_name}' quality floor"
            if policy.task_aware_floor
            else f"task '{task_type}', quality '{quality}'"
        )
        return RouteDecision(
            selected=None,
            reason="no_suitable_model",
            ranked=[],
            fallback=[],
            explanation=f"No model satisfies {constraint}, and policy '{policy.name}'.",
        )

    if policy.is_default:
        # pool is already cheapest-first, so pool[0] == model_selector.select(...).
        winner = pool[0]
        ranked = [(m.external_model_id, round(-_cost(m), 6)) for m in pool]
        explanation = (
            f"Selected the cheapest capable model for task '{task_type}', quality '{quality}'."
        )
    else:
        ordered = sorted(pool, key=lambda m: _score(m, policy, pool, scores), reverse=True)
        winner = ordered[0]
        ranked = [(m.external_model_id, round(_score(m, policy, pool, scores), 4)) for m in ordered]
        if policy.task_aware_floor:
            explanation = _explain_auto(winner, policy, scores, task_type, floor_name, floor_met)
        else:
            explanation = _explain(winner, policy, scores)

    fallback = [mid for mid, _ in ranked if mid != winner.external_model_id]
    return RouteDecision(
        selected=winner,
        reason=f"policy:{policy.name}",
        ranked=ranked,
        fallback=fallback,
        explanation=explanation,
    )
