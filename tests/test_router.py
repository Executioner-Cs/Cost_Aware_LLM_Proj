"""
Integration tests for core/router.py using mocked provider adapters.
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ModelRegistry, ConnectedAccount
from db.session import create_all_tables
from schemas.routing import RouteRequest


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def populated_session(db_session, tmp_path):
    """Session with one connected account + two models."""
    from datetime import datetime, timezone

    account = ConnectedAccount(
        id="acc-1",
        provider="openai",
        display_name="Test Account",
        auth_method="pat",
        encrypted_token="encrypted_fake",
        status="active",
        connected_at=datetime.now(timezone.utc).isoformat(),
    )
    db_session.add(account)

    m1 = ModelRegistry(
        id="m-1",
        account_id="acc-1",
        provider="openai",
        external_model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        tier="small",
        context_window=128_000,
        cost_per_1m_input=0.15,
        cost_per_1m_output=0.60,
        supports_json=1,
        supports_tools=1,
        supports_vision=1,
        enabled=1,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    db_session.add(m1)
    db_session.commit()
    return db_session, tmp_path


def test_route_cache_miss_calls_provider(populated_session):
    session, tmp_path = populated_session

    from providers.base import GenerateResult
    fake_result = GenerateResult(
        response_text="Paris",
        input_tokens=10,
        output_tokens=5,
        latency_ms=300,
        model_id="gpt-4o-mini",
        provider="openai",
    )

    with (
        patch("core.router.get_home", return_value=tmp_path),
        patch("core.router.load_config", return_value={"cache": {"enabled": False}}),
        patch("core.router.decrypt", return_value="fake-api-key"),
        patch("providers.openai.adapter.OpenAIAdapter.generate", return_value=fake_result),
    ):
        from core.router import route
        result = route(RouteRequest(prompt="What is the capital of France?"), session)

    assert result.response_text == "Paris"
    assert not result.cache_hit
    assert result.provider == "openai"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_route_dry_run(populated_session):
    session, tmp_path = populated_session

    with (
        patch("core.router.get_home", return_value=tmp_path),
        patch("core.router.load_config", return_value={"cache": {"enabled": False}}),
    ):
        from core.router import route
        result = route(RouteRequest(prompt="Hello", dry_run=True), session)

    assert result.response_text is None
    assert result.model_id == "gpt-4o-mini"
    assert result.estimated_cost_usd >= 0


def test_route_no_models_raises(db_session, tmp_path):
    with (
        patch("core.router.get_home", return_value=tmp_path),
        patch("core.router.load_config", return_value={"cache": {"enabled": False}}),
    ):
        from core.router import route
        with pytest.raises(RuntimeError, match="No models"):
            route(RouteRequest(prompt="test"), db_session)


# --------------------------------------------------------------------------- #
# Scorecard-aware (opt-in) routing through the full pipeline.
# --------------------------------------------------------------------------- #

def _add_premium_model(session):
    from datetime import datetime, timezone
    session.add(ModelRegistry(
        id="m-2", account_id="acc-1", provider="openai", external_model_id="premium",
        display_name="Premium", tier="small", context_window=128_000,
        cost_per_1m_input=10.0, cost_per_1m_output=20.0,
        supports_json=1, supports_tools=1, supports_vision=1, enabled=1,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    ))


def _add_scorecard(session, model_id, score, task_set_id="ts-1"):
    from datetime import datetime, timezone
    from db.models import Scorecard
    import uuid
    session.add(Scorecard(
        id=str(uuid.uuid4()), run_id="run-1", task_set_id=task_set_id,
        provider="openai", model_id=model_id, tasks_total=1,
        tasks_passed=int(round(score)), score=score,
        avg_latency_ms=1.0, avg_cost_usd=0.0,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))


def test_route_benchmarked_selects_scored_model_over_cheapest(populated_session):
    session, tmp_path = populated_session
    _add_premium_model(session)                 # pricier than gpt-4o-mini
    _add_scorecard(session, "premium", 1.0)     # premium earned a high score
    _add_scorecard(session, "gpt-4o-mini", 0.0)
    session.commit()

    with (
        patch("core.router.get_home", return_value=tmp_path),
        patch("core.router.load_config", return_value={"cache": {"enabled": False}}),
    ):
        from core.router import route
        default = route(RouteRequest(prompt="hi", dry_run=True), session)
        assert default.model_id == "gpt-4o-mini"            # cheapest-capable

        bench = route(RouteRequest(prompt="hi", dry_run=True, policy="benchmarked"), session)
        assert bench.model_id == "premium"                  # scorecard wins
        assert bench.route_explanation and "premium" in bench.route_explanation


def test_route_benchmarked_unknown_task_set_raises(populated_session):
    session, tmp_path = populated_session
    with (
        patch("core.router.get_home", return_value=tmp_path),
        patch("core.router.load_config", return_value={"cache": {"enabled": False}}),
    ):
        from core.router import route
        with pytest.raises(RuntimeError, match="not found"):
            route(
                RouteRequest(prompt="hi", dry_run=True, policy="benchmarked", task_set="nope"),
                session,
            )


def test_route_benchmarked_policy_bypasses_exact_cache(populated_session):
    session, tmp_path = populated_session
    from providers.base import GenerateResult
    fake = GenerateResult(
        response_text="X", input_tokens=10, output_tokens=5,
        latency_ms=100, model_id="gpt-4o-mini", provider="openai",
    )
    cfg = {"cache": {"enabled": True, "mode": "exact"}}
    with (
        patch("core.router.get_home", return_value=tmp_path),
        patch("core.router.load_config", return_value=cfg),
        patch("core.router.decrypt", return_value="fake-api-key"),
        patch("providers.openai.adapter.OpenAIAdapter.generate", return_value=fake),
    ):
        from core.router import route
        assert route(RouteRequest(prompt="hi"), session).cache_hit is False   # miss -> stores
        assert route(RouteRequest(prompt="hi"), session).cache_hit is True    # default hit
        # benchmarked must bypass the cache even though an entry exists.
        bypass = route(RouteRequest(prompt="hi", policy="benchmarked"), session)
        assert bypass.cache_hit is False
