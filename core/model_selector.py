"""
Model selector — pure logic, no I/O.

Given task constraints, returns the cheapest model that satisfies all requirements.
"""
from __future__ import annotations

from typing import Optional

from db.models import ModelRegistry


TIER_ORDER = {"small": 0, "balanced": 1, "large": 2}

# quality → minimum tier
QUALITY_MIN_TIER: dict[str, str] = {
    "cheap": "small",
    "balanced": "small",
    "best": "large",
}

# quality → maximum tier
QUALITY_MAX_TIER: dict[str, str] = {
    "cheap": "small",
    "balanced": "balanced",
    "best": "large",
}

# task_type → required capabilities
TASK_CAPABILITIES: dict[str, dict] = {
    "json_extract": {"supports_json": True},
    "vision": {"supports_vision": True},
    "tools": {"supports_tools": True},
    "reasoning": {},
    "simple": {},
}


def _cost_score(m: ModelRegistry) -> float:
    """Combined input+output price proxy used to rank cheapest-first."""
    return (m.cost_per_1m_input or 0.0) + (m.cost_per_1m_output or 0.0)


def candidates(
    models: list[ModelRegistry],
    task_type: str,
    quality: str = "balanced",
    input_tokens: int = 0,
) -> list[ModelRegistry]:
    """Enabled models satisfying all hard constraints, cheapest-first.

    Constraints:
      - enabled == 1
      - context_window >= input_tokens (with 20% headroom for output)
      - tier within quality range
      - capability flags required by task_type
    """
    caps = TASK_CAPABILITIES.get(task_type, {})
    min_tier = TIER_ORDER[QUALITY_MIN_TIER.get(quality, "small")]
    max_tier = TIER_ORDER[QUALITY_MAX_TIER.get(quality, "large")]

    pool: list[ModelRegistry] = []
    for m in models:
        if not m.enabled:
            continue
        tier_val = TIER_ORDER.get(m.tier, 99)
        if tier_val < min_tier or tier_val > max_tier:
            continue
        if m.context_window and m.context_window < input_tokens * 1.2:
            continue
        if caps.get("supports_json") and not m.supports_json:
            continue
        if caps.get("supports_vision") and not m.supports_vision:
            continue
        if caps.get("supports_tools") and not m.supports_tools:
            continue
        pool.append(m)

    pool.sort(key=_cost_score)
    return pool


def select(
    models: list[ModelRegistry],
    task_type: str,
    quality: str = "balanced",
    input_tokens: int = 0,
) -> Optional[ModelRegistry]:
    """Return the cheapest enabled model satisfying all constraints, or None."""
    pool = candidates(models, task_type, quality, input_tokens)
    return pool[0] if pool else None
