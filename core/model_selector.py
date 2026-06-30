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

# task_type → minimum tier the Auto preset requires (its quality floor). Simple
# work may run on a small model; tasks where a weak model commonly fails (JSON
# extraction, reasoning, vision, tool use) are floored at 'balanced'. Auto never
# floors at 'large', so it does not become an always-biggest-model mode; raising
# the floor to 'large' is the job of the 'best'/'deep' presets, not Auto.
TASK_QUALITY_FLOOR: dict[str, str] = {
    "simple": "small",
    "json_extract": "balanced",
    "reasoning": "balanced",
    "vision": "balanced",
    "tools": "balanced",
}


def auto_floor_tier(task_type: str, quality: str = "balanced") -> str:
    """The Auto preset's effective quality floor: the higher of the task's floor and
    the quality knob's minimum tier.

    So a complex task is never floored below 'balanced', and an explicit
    ``--quality best`` raises the floor to 'large' rather than being silently
    ignored. A lower quality knob ('cheap') never drops the floor below the task's.
    """
    task_floor = TASK_QUALITY_FLOOR.get(task_type, "small")
    quality_floor = QUALITY_MIN_TIER.get(quality, "small")
    return task_floor if TIER_ORDER[task_floor] >= TIER_ORDER[quality_floor] else quality_floor


def _cost_score(m: ModelRegistry) -> float:
    """Combined input+output price proxy used to rank cheapest-first."""
    return (m.cost_per_1m_input or 0.0) + (m.cost_per_1m_output or 0.0)


def capable_models(
    models: list[ModelRegistry],
    task_type: str,
    input_tokens: int = 0,
) -> list[ModelRegistry]:
    """Enabled models meeting capability and context constraints, cheapest-first,
    across ALL tiers.

    This is the candidate pool for task-aware policies (the Auto preset), which
    apply their own tier floor instead of the quality min/max tier range that
    ``candidates`` enforces. It does not look at the quality knob at all. The
    per-model checks are the same ones ``candidates`` historically applied inline.
    """
    caps = TASK_CAPABILITIES.get(task_type, {})
    pool: list[ModelRegistry] = []
    for m in models:
        if not m.enabled:
            continue
        if caps.get("supports_json") and not m.supports_json:
            continue
        if caps.get("supports_vision") and not m.supports_vision:
            continue
        if caps.get("supports_tools") and not m.supports_tools:
            continue
        if m.context_window and m.context_window < input_tokens * 1.2:
            continue
        pool.append(m)
    pool.sort(key=_cost_score)
    return pool


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
    min_tier = TIER_ORDER[QUALITY_MIN_TIER.get(quality, "small")]
    max_tier = TIER_ORDER[QUALITY_MAX_TIER.get(quality, "large")]
    return [
        m for m in capable_models(models, task_type, input_tokens)
        if min_tier <= TIER_ORDER.get(m.tier, 99) <= max_tier
    ]


def select(
    models: list[ModelRegistry],
    task_type: str,
    quality: str = "balanced",
    input_tokens: int = 0,
) -> Optional[ModelRegistry]:
    """Return the cheapest enabled model satisfying all constraints, or None."""
    pool = candidates(models, task_type, quality, input_tokens)
    return pool[0] if pool else None
