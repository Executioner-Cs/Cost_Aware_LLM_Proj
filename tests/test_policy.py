"""
Routing policy engine: the default policy is byte-for-byte cheapest-capable
(behavior preserved), explicit policies change ranking deterministically, and a
route explanation + fallback chain is produced.
"""
from __future__ import annotations

from core import model_selector
from core.policy import decide, get_policy, DEFAULT_POLICY, POLICIES, RoutingPolicy
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
# Behavior preservation: default policy == cheapest-capable
# --------------------------------------------------------------------------- #

def test_default_policy_matches_cheapest_capable():
    models = [_m("cheap", cost=0.1), _m("mid", cost=1.0), _m("pricey", cost=5.0)]
    decision = decide(models, "simple", "balanced")
    assert decision.selected.external_model_id == "cheap"
    assert decision.selected.external_model_id == model_selector.select(models, "simple", "balanced").external_model_id


def test_default_decide_equals_select_across_inputs():
    models = [
        _m("a", tier="small", cost=2.0),
        _m("b", tier="balanced", cost=1.0),
        _m("c", tier="large", cost=10.0),
        _m("nojson", tier="small", cost=0.1, json=0),
    ]
    for quality in ("cheap", "balanced", "best"):
        for task in ("simple", "reasoning", "json_extract", "tools"):
            d = decide(models, task, quality)
            s = model_selector.select(models, task, quality)
            assert (d.selected.external_model_id if d.selected else None) == \
                   (s.external_model_id if s else None), (task, quality)


def test_candidates_cost_sorted_and_select_is_first():
    models = [_m("pricey", cost=5.0), _m("cheap", cost=0.1)]
    pool = model_selector.candidates(models, "simple", "balanced")
    assert [m.external_model_id for m in pool] == ["cheap", "pricey"]
    assert model_selector.select(models, "simple", "balanced").external_model_id == "cheap"


# --------------------------------------------------------------------------- #
# Hard filters
# --------------------------------------------------------------------------- #

def test_privacy_first_requires_local_source():
    models = [_m("gpt", provider="openai", cost=0.1), _m("llama3", provider="ollama", cost=0.0)]
    decision = decide(models, "simple", "balanced", policy=POLICIES["privacy-first"])
    assert decision.selected.external_model_id == "llama3"
    assert decision.selected.provider == "ollama"


def test_privacy_first_without_local_returns_none():
    decision = decide([_m("gpt", provider="openai")], "simple", "balanced", policy=POLICIES["privacy-first"])
    assert decision.selected is None
    assert decision.reason == "no_suitable_model"
    assert decision.explanation


def test_require_json_filters_out_cheaper_non_json():
    policy = RoutingPolicy(name="json", require_json=True)
    models = [_m("nojson", json=0, cost=0.1), _m("json", json=1, cost=5.0)]
    decision = decide(models, "simple", "balanced", policy=policy)
    assert decision.selected.external_model_id == "json"


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

def test_quality_first_prefers_higher_tier_over_cheapest():
    models = [_m("small_cheap", tier="small", cost=0.1), _m("balanced_pricey", tier="balanced", cost=5.0)]
    assert decide(models, "simple", "balanced").selected.external_model_id == "small_cheap"  # default = cheapest
    quality = decide(models, "simple", "balanced", policy=POLICIES["quality-first"])
    assert quality.selected.external_model_id == "balanced_pricey"  # higher tier wins


# --------------------------------------------------------------------------- #
# Explanation + fallback
# --------------------------------------------------------------------------- #

def test_explanation_and_fallback_chain():
    models = [_m("a", cost=0.1), _m("b", cost=1.0), _m("c", cost=5.0)]
    decision = decide(models, "simple", "balanced")
    assert decision.explanation
    assert decision.selected.external_model_id == "a"
    assert decision.fallback == ["b", "c"]                      # ordered alternatives, winner excluded
    ranked_ids = [mid for mid, _ in decision.ranked]
    assert len(ranked_ids) == len(set(ranked_ids))             # no duplicate candidate identities


def test_get_policy_resolves_names_safely():
    assert get_policy(None) is DEFAULT_POLICY
    assert get_policy("privacy-first").require_local is True
    assert get_policy("does-not-exist") is DEFAULT_POLICY      # safe fallback, never raises


# --------------------------------------------------------------------------- #
# Scorecard-aware (opt-in) policy. Default stays unchanged with the new fields.
# --------------------------------------------------------------------------- #

def test_default_policy_still_default_with_scorecard_fields():
    assert DEFAULT_POLICY.is_default is True
    assert POLICIES["benchmarked"].is_default is False
    assert get_policy("benchmarked").prefer_scorecards is True


def test_benchmarked_policy_prefers_high_scored_over_cheaper():
    models = [_m("cheap", cost=0.1), _m("good", cost=5.0)]
    # Without a policy the cheap model wins (behavior preserved).
    assert decide(models, "simple", "balanced").selected.external_model_id == "cheap"
    # With scorecards, the model that scored well on the user's tasks wins.
    scored = decide(
        models, "simple", "balanced",
        policy=POLICIES["benchmarked"], scores={"good": 0.95, "cheap": 0.2},
    )
    assert scored.selected.external_model_id == "good"
    assert "scored 95%" in scored.explanation


def test_benchmarked_policy_no_scores_falls_back_to_cheapest():
    models = [_m("cheap", cost=0.1), _m("pricey", cost=5.0)]
    decision = decide(models, "simple", "balanced", policy=POLICIES["benchmarked"], scores={})
    assert decision.selected.external_model_id == "cheap"        # explicit no-scorecard fallback
    assert "fell back to cheapest-capable" in decision.explanation


def test_benchmarked_policy_scored_beats_unscored_cheaper():
    # 'good' has a scorecard, 'cheap' does not: the scored model still wins.
    models = [_m("cheap", cost=0.1), _m("good", cost=5.0)]
    decision = decide(
        models, "simple", "balanced",
        policy=POLICIES["benchmarked"], scores={"good": 0.9},
    )
    assert decision.selected.external_model_id == "good"
