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
    # Declared but not yet scored (no data until benchmark scorecards exist).
    weight_latency: float = 0.0
    weight_reliability: float = 0.0

    @property
    def is_default(self) -> bool:
        return (
            not self.require_local and not self.require_json and not self.require_tools
            and self.weight_quality == 0.0 and self.weight_context == 0.0
            and self.weight_latency == 0.0 and self.weight_reliability == 0.0
        )


DEFAULT_POLICY = RoutingPolicy()

# Named policies the engine can resolve. Kept small and explicit.
POLICIES: dict[str, RoutingPolicy] = {
    "default": DEFAULT_POLICY,
    "cheapest": DEFAULT_POLICY,
    "privacy-first": RoutingPolicy(name="privacy-first", require_local=True),
    "quality-first": RoutingPolicy(name="quality-first", weight_quality=2.0, weight_cost=0.5),
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


def _score(m: ModelRegistry, policy: RoutingPolicy, pool: list[ModelRegistry]) -> float:
    max_cost = max((_cost(x) for x in pool), default=0.0) or 1.0
    max_ctx = max((x.context_window or 0 for x in pool), default=0) or 1
    cost_term = policy.weight_cost * (1.0 - _cost(m) / max_cost)              # cheaper -> higher
    quality_term = policy.weight_quality * (TIER_ORDER.get(m.tier, 0) / 2.0)  # higher tier -> higher
    context_term = policy.weight_context * ((m.context_window or 0) / max_ctx)
    return cost_term + quality_term + context_term


def _explain(winner: ModelRegistry, policy: RoutingPolicy) -> str:
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
    detail = f" under {', '.join(prefs)}" if prefs else ""
    return (
        f"Policy '{policy.name}' selected {winner.external_model_id} "
        f"({winner.provider}, tier {winner.tier}){detail}."
    )


def decide(
    models: list[ModelRegistry],
    task_type: str,
    quality: str = "balanced",
    input_tokens: int = 0,
    policy: RoutingPolicy = DEFAULT_POLICY,
) -> RouteDecision:
    """Choose a model under *policy* and explain the choice.

    For the default policy the winner is the cheapest capable model, identical to
    ``model_selector.select``. Explicit policies score the candidate pool.
    """
    pool = [
        m for m in model_selector.candidates(models, task_type, quality, input_tokens)
        if _passes_hard_filters(m, policy)
    ]

    if not pool:
        return RouteDecision(
            selected=None,
            reason="no_suitable_model",
            ranked=[],
            fallback=[],
            explanation=(
                f"No model satisfies task '{task_type}', quality '{quality}', "
                f"and policy '{policy.name}'."
            ),
        )

    if policy.is_default:
        # pool is already cheapest-first, so pool[0] == model_selector.select(...).
        winner = pool[0]
        ranked = [(m.external_model_id, round(-_cost(m), 6)) for m in pool]
        explanation = (
            f"Selected the cheapest capable model for task '{task_type}', quality '{quality}'."
        )
    else:
        ordered = sorted(pool, key=lambda m: _score(m, policy, pool), reverse=True)
        winner = ordered[0]
        ranked = [(m.external_model_id, round(_score(m, policy, pool), 4)) for m in ordered]
        explanation = _explain(winner, policy)

    fallback = [mid for mid, _ in ranked if mid != winner.external_model_id]
    return RouteDecision(
        selected=winner,
        reason=f"policy:{policy.name}",
        ranked=ranked,
        fallback=fallback,
        explanation=explanation,
    )
