"""Constraint-aware Auto preset.

Auto sets a per-task quality floor so it does not route a complex task to the
cheapest weak model, yet still picks the cheapest model above the floor for simple
work (no always-biggest, no always-cheapest). It uses benchmark scorecards when
present, falls back honestly to cost when they are absent, respects the local-only
hard presets, and explains the choice. Existing policies are covered by
``test_policy.py`` and must stay unchanged.
"""
from __future__ import annotations

from core import model_selector
from core.policy import (
    AUTO_POLICY,
    DEFAULT_POLICY,
    POLICIES,
    PRESET_NOTES,
    decide,
    get_policy,
)
from db.models import ModelRegistry


def _m(ext, *, provider="openai", tier="small", cost=1.0, ctx=128_000,
       json=1, tools=1, vision=0, enabled=1):
    return ModelRegistry(
        id=ext, account_id="a", provider=provider, external_model_id=ext,
        display_name=ext, tier=tier, context_window=ctx,
        cost_per_1m_input=cost, cost_per_1m_output=cost * 2,
        supports_json=json, supports_tools=tools, supports_vision=vision,
        enabled=enabled, discovered_at="2026-01-01",
    )


# --------------------------------------------------------------------------- #
# Quality floor: no weak model for complex work, cheap model for simple work
# --------------------------------------------------------------------------- #

def test_auto_floors_complex_task_above_small_when_better_exists():
    # Required test 1: a reasoning task must not land on the cheap small model when
    # a balanced model is available.
    models = [_m("small_cheap", tier="small", cost=0.1), _m("bal", tier="balanced", cost=1.0)]
    decision = decide(models, "reasoning", policy=AUTO_POLICY)
    assert decision.selected.external_model_id == "bal"


def test_auto_keeps_cheap_small_for_simple_task():
    # Required test 2: simple low-risk work still gets the cheapest small model.
    models = [_m("small_cheap", tier="small", cost=0.1), _m("bal", tier="balanced", cost=1.0)]
    decision = decide(models, "simple", policy=AUTO_POLICY)
    assert decision.selected.external_model_id == "small_cheap"


def test_auto_does_not_pick_biggest_when_floor_already_met():
    # Devil's advocate: Auto is not a hidden always-biggest mode. With no scorecards,
    # the cheapest model that clears the floor wins, not the large one.
    models = [_m("bal", tier="balanced", cost=1.0), _m("large", tier="large", cost=10.0)]
    decision = decide(models, "reasoning", policy=AUTO_POLICY)
    assert decision.selected.external_model_id == "bal"


def test_auto_floor_not_met_uses_best_available_honestly():
    # Only small models exist for a reasoning task (floor 'balanced' unreachable):
    # Auto routes to the best available and says the floor was not met.
    models = [_m("small_a", tier="small", cost=0.1), _m("small_b", tier="small", cost=0.5)]
    decision = decide(models, "reasoning", policy=AUTO_POLICY)
    assert decision.selected is not None
    assert "no available" in decision.explanation
    assert "best available" in decision.explanation


# --------------------------------------------------------------------------- #
# --quality interacts with the floor instead of being silently ignored
# --------------------------------------------------------------------------- #

def test_auto_best_quality_raises_floor_to_large():
    # `--quality best` with Auto raises the floor to 'large' (not silently dropped),
    # so the large model wins even though balanced would otherwise clear the floor.
    models = [_m("bal", tier="balanced", cost=1.0), _m("large", tier="large", cost=10.0)]
    decision = decide(models, "reasoning", quality="best", policy=AUTO_POLICY)
    assert decision.selected.external_model_id == "large"
    assert "large" in decision.explanation


def test_auto_cheap_quality_does_not_drop_below_task_floor():
    # `--quality cheap` must not lower the floor below the task's own floor: a
    # reasoning task still refuses the small model when a balanced one exists.
    models = [_m("small_cheap", tier="small", cost=0.1), _m("bal", tier="balanced", cost=1.0)]
    decision = decide(models, "reasoning", quality="cheap", policy=AUTO_POLICY)
    assert decision.selected.external_model_id == "bal"


# --------------------------------------------------------------------------- #
# Local / private hard modes
# --------------------------------------------------------------------------- #

def test_private_preset_routes_to_local_source():
    # Required test 3: the private/local presets are hard local-only.
    models = [_m("gpt", provider="openai", cost=0.1), _m("llama3", provider="ollama", cost=0.0)]
    for preset in ("private", "local"):
        decision = decide(models, "simple", policy=POLICIES[preset])
        assert decision.selected.external_model_id == "llama3"
        assert decision.selected.provider == "ollama"


def test_private_preset_never_falls_back_to_cloud():
    # Required test 4: with only a cloud model and private mode, routing refuses
    # rather than silently sending data to the cloud.
    models = [_m("gpt", provider="openai", cost=0.1)]
    decision = decide(models, "simple", policy=POLICIES["private"])
    assert decision.selected is None
    assert decision.reason == "no_suitable_model"


# --------------------------------------------------------------------------- #
# Scorecard evidence vs honest cost fallback
# --------------------------------------------------------------------------- #

def test_auto_uses_scorecard_evidence_when_available():
    # Required test 5: a model that scored well on the user's tasks wins over a
    # cheaper one of the same tier.
    models = [_m("bal_cheap", tier="balanced", cost=1.0), _m("bal_good", tier="balanced", cost=5.0)]
    decision = decide(models, "reasoning", policy=AUTO_POLICY, scores={"bal_good": 0.9, "bal_cheap": 0.2})
    assert decision.selected.external_model_id == "bal_good"
    assert "scored 90%" in decision.explanation


def test_auto_falls_back_to_cost_when_no_scorecards():
    # Required test 6: without scorecards Auto picks the cheapest above the floor and
    # says the choice has no benchmark evidence.
    models = [_m("bal_cheap", tier="balanced", cost=1.0), _m("bal_pricey", tier="balanced", cost=5.0)]
    decision = decide(models, "reasoning", policy=AUTO_POLICY, scores={})
    assert decision.selected.external_model_id == "bal_cheap"
    assert "No benchmark evidence" in decision.explanation


def test_auto_scorecard_crossover_threshold():
    # Pin the weights (weight_scorecard=2.0, weight_cost=1.0): the cheapest model's
    # cost bonus is 0.8 over this spread, so a 5x-pricier model needs a score above
    # 0.4 to win. Pin both sides so the balance is intentional, not accidental.
    models = [_m("cheap", tier="balanced", cost=1.0), _m("pricey", tier="balanced", cost=5.0)]
    below = decide(models, "reasoning", policy=AUTO_POLICY, scores={"pricey": 0.39})
    assert below.selected.external_model_id == "cheap"
    above = decide(models, "reasoning", policy=AUTO_POLICY, scores={"pricey": 0.41})
    assert above.selected.external_model_id == "pricey"


# --------------------------------------------------------------------------- #
# Empty / fully-filtered pools return no_suitable_model, never crash
# --------------------------------------------------------------------------- #

def test_auto_empty_model_list_returns_no_suitable_model():
    decision = decide([], "reasoning", policy=AUTO_POLICY)
    assert decision.selected is None
    assert decision.reason == "no_suitable_model"


def test_auto_all_disabled_returns_no_suitable_model():
    models = [_m("x", enabled=0), _m("y", enabled=0)]
    decision = decide(models, "reasoning", policy=AUTO_POLICY)
    assert decision.selected is None


def test_auto_context_too_small_returns_no_suitable_model():
    models = [_m("tiny", tier="balanced", ctx=100)]
    decision = decide(models, "reasoning", input_tokens=200, policy=AUTO_POLICY)
    assert decision.selected is None
    assert decision.reason == "no_suitable_model"


def test_auto_capability_filter_removes_all_models():
    # A vision task with no vision-capable model: the capability filter empties the
    # pool before the floor is even considered.
    models = [_m("bal", tier="balanced", vision=0)]
    decision = decide(models, "vision", policy=AUTO_POLICY)
    assert decision.selected is None


def test_auto_vision_floor_not_met_routes_to_small_vision_model():
    # Only a small vision-capable model exists; the 'balanced' floor is unreachable,
    # so Auto routes to it and says the floor was not met.
    models = [_m("vis_small", tier="small", vision=1)]
    decision = decide(models, "vision", policy=AUTO_POLICY)
    assert decision.selected.external_model_id == "vis_small"
    assert "no available" in decision.explanation


def test_auto_empty_pool_explanation_does_not_misname_quality():
    # The no-model explanation for Auto must not claim a 'quality' constraint Auto
    # does not use; it names the quality floor instead.
    decision = decide([_m("gpt", provider="openai")], "simple", policy=POLICIES["private"])
    assert decision.selected is None
    models = [_m("tiny", tier="balanced", ctx=100)]
    floor_decision = decide(models, "reasoning", input_tokens=200, policy=AUTO_POLICY)
    assert "quality floor" in floor_decision.explanation


# --------------------------------------------------------------------------- #
# Explanation honesty
# --------------------------------------------------------------------------- #

def test_auto_explanation_mentions_task_floor_and_tradeoff():
    # Required test 7: the explanation names the task type, the quality floor, and
    # the cheapest-that-clears-it tradeoff.
    models = [_m("small_cheap", tier="small", cost=0.1), _m("bal", tier="balanced", cost=1.0)]
    explanation = decide(models, "reasoning", policy=AUTO_POLICY).explanation
    assert "reasoning" in explanation
    assert "quality floor" in explanation
    assert "balanced" in explanation
    assert "cheapest" in explanation and "clears it" in explanation


# --------------------------------------------------------------------------- #
# Preset resolution and policy shape
# --------------------------------------------------------------------------- #

def test_preset_names_resolve():
    assert get_policy("auto") is AUTO_POLICY
    assert get_policy("auto").task_aware_floor is True
    assert get_policy("fast") is AUTO_POLICY            # deferred alias, see PRESET_NOTES
    assert get_policy("cheap") is DEFAULT_POLICY
    assert get_policy("best").weight_quality == 2.0
    assert get_policy("deep").weight_quality == 2.0
    assert get_policy("private").require_local is True
    assert get_policy("local").require_local is True
    assert "fast" in PRESET_NOTES


def test_preset_synonyms_share_one_object():
    # Synonyms must alias the same object so they cannot drift apart (same pattern
    # as the existing default/cheapest synonyms).
    assert get_policy("private") is get_policy("local") is get_policy("privacy-first")
    assert get_policy("best") is get_policy("deep") is get_policy("quality-first")
    assert get_policy("cheap") is get_policy("cheapest") is DEFAULT_POLICY


def test_auto_is_not_the_default_policy():
    # Auto is opt-in this branch: it must not equal the cheapest-capable default,
    # and the default must stay default (so the bare-route + cache path is unchanged).
    assert AUTO_POLICY.is_default is False
    assert DEFAULT_POLICY.is_default is True
    assert POLICIES["private"].is_default is False


# --------------------------------------------------------------------------- #
# capable_models / floor helper
# --------------------------------------------------------------------------- #

def test_capable_models_spans_all_tiers_unlike_candidates():
    models = [_m("s", tier="small", cost=0.1), _m("b", tier="balanced", cost=1.0), _m("l", tier="large", cost=9.0)]
    capable_ids = {m.external_model_id for m in model_selector.capable_models(models, "simple")}
    balanced_ids = {m.external_model_id for m in model_selector.candidates(models, "simple", "balanced")}
    assert capable_ids == {"s", "b", "l"}          # all tiers
    assert "l" not in balanced_ids                 # 'balanced' quality caps out the large tier (unchanged)


def test_auto_floor_tier_combines_task_and_quality():
    assert model_selector.auto_floor_tier("simple") == "small"
    assert model_selector.auto_floor_tier("reasoning") == "balanced"
    assert model_selector.auto_floor_tier("simple", "best") == "large"      # quality raises it
    assert model_selector.auto_floor_tier("reasoning", "cheap") == "balanced"  # task floor holds
