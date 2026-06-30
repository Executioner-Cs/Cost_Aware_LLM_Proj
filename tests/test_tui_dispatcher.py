"""
Tests for cli/tui/dispatcher.py — pure logic, no Textual rendering.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ConnectedAccount, ModelRegistry
from cli.tui.dispatcher import SessionState, Dispatcher


@pytest.fixture
def tmp_state(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    state = SessionState(
        session=session,
        home=tmp_path,
        config={"cache": {"enabled": True, "similarity_threshold": 0.92}},
    )
    state.refresh_stats()

    yield state, session, tmp_path
    session.close()


def test_refresh_stats_counts_enabled_models(tmp_state):
    """model_count reflects enabled models so the status bar is honest, not a
    hardcoded 0."""
    state, session, home = tmp_state
    assert state.model_count == 0
    session.add(ModelRegistry(
        id="m1", provider="ollama", external_model_id="llama3",
        tier="balanced", enabled=1, discovered_at="2026-01-01T00:00:00",
    ))
    session.commit()
    state.refresh_stats()
    assert state.model_count == 1


def test_empty_command_returns_nothing(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    assert d.dispatch("") == []
    assert d.dispatch("   ") == []


def test_help_returns_panel(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    result = d.dispatch("help")
    assert len(result) == 1
    from rich.panel import Panel
    assert isinstance(result[0], Panel)


def test_quit_returns_sentinel(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    for cmd in ("quit", "exit", "q"):
        assert d.dispatch(cmd) == ["__quit__"]


def test_clear_returns_sentinel(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    assert d.dispatch("clear") == ["__clear__"]


def test_unknown_command_returns_error_text(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    result = d.dispatch("foobar")
    assert len(result) == 1
    assert isinstance(result[0], Text)
    assert "Unknown" in result[0].plain


def test_quality_command_updates_state(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    d.dispatch("quality best")
    assert state.quality == "best"


def test_quality_invalid_shows_usage(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    result = d.dispatch("quality turbo")
    assert isinstance(result[0], Text)
    assert state.quality == "balanced"   # unchanged


def test_accounts_list_no_accounts(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    result = d.dispatch("accounts list")
    assert isinstance(result[0], Text)


def test_model_list_no_models(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    result = d.dispatch("model list")
    assert isinstance(result[0], Text)


def test_model_list_with_models(tmp_state):
    from datetime import datetime, timezone
    state, session, home = tmp_state

    account = ConnectedAccount(
        id="acc-test", provider="openai", display_name="Test",
        auth_method="pat", encrypted_token="fake", status="active",
        connected_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(account)
    m = ModelRegistry(
        id="m-test", account_id="acc-test", provider="openai",
        external_model_id="gpt-4o-mini", display_name="GPT-4o Mini",
        tier="small", context_window=128_000,
        cost_per_1m_input=0.15, cost_per_1m_output=0.60,
        supports_json=1, supports_tools=1, supports_vision=1, enabled=1,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(m)
    session.commit()

    d = Dispatcher(state)
    from rich.table import Table
    result = d.dispatch("model list")
    assert isinstance(result[0], Table)


def test_trace_list_empty(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    result = d.dispatch("trace list")
    assert isinstance(result[0], Text)


def test_cache_stats_exact(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    # Exact cache (default): stats render with no vector store, no crash.
    result = d.dispatch("cache stats")
    assert len(result) >= 1


def test_route_no_models_returns_error(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    result = d.dispatch('route "hello world"')
    # Should return error text (no models in DB)
    assert any(isinstance(r, Text) for r in result)


# ── Workbench: help, benchmarks, scorecard routing ───────────────────────────

def test_help_mentions_workbench_commands(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    help_text = d.dispatch("help")[0].renderable
    assert "Benchmarks" in help_text and "benchmark run" in help_text
    assert "--policy" in help_text
    assert "exact-match response cache" in help_text  # stale "semantic cache" line fixed


def test_route_policy_flag_parses(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    # No models, so it errors after parsing; the point is the flags parse (no usage text).
    result = d.dispatch('route "hi" --policy benchmarked --task-set qa')
    assert any(isinstance(r, Text) for r in result)
    assert all("Usage:" not in r.plain for r in result if isinstance(r, Text))


def test_benchmark_create_then_scorecards_empty(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    created = d.dispatch("benchmark create qa")
    assert isinstance(created[0], Text) and "Created" in created[0].plain
    empty = d.dispatch("benchmark scorecards --task-set qa")
    assert isinstance(empty[0], Text) and "No scorecards" in empty[0].plain


def test_benchmark_add_task_requires_expected(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    d.dispatch("benchmark create qa")
    result = d.dispatch('benchmark add-task qa "2+2?" --grader exact')
    assert isinstance(result[0], Text) and "needs --expected" in result[0].plain


def test_benchmark_run_no_models(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    d.dispatch("benchmark create qa")
    d.dispatch('benchmark add-task qa "2+2?" --expected 4 --grader exact')
    result = d.dispatch("benchmark run qa")
    assert isinstance(result[0], Text) and "No matching enabled models" in result[0].plain


def test_benchmark_run_full_flow(tmp_state, monkeypatch):
    from datetime import datetime, timezone
    from providers.base import GenerateResult
    from rich.table import Table

    state, session, home = tmp_state
    session.add(ConnectedAccount(
        id="acc", provider="openai", display_name="t", auth_method="pat",
        encrypted_token="fake", status="active",
        connected_at=datetime.now(timezone.utc).isoformat(),
    ))
    session.add(ModelRegistry(
        id="m", account_id="acc", provider="openai", external_model_id="gpt-4o-mini",
        display_name="x", tier="small", context_window=128_000,
        cost_per_1m_input=0.1, cost_per_1m_output=0.2,
        supports_json=1, supports_tools=1, supports_vision=0, enabled=1,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    ))
    session.commit()

    monkeypatch.setattr("utils.crypto.decrypt", lambda t: "k")
    monkeypatch.setattr(
        "providers.source.ModelSource.generate",
        lambda self, prompt, model_id, api_key, **kw: GenerateResult(
            response_text="4", input_tokens=3, output_tokens=1,
            latency_ms=10, model_id=model_id, provider="openai",
        ),
    )

    d = Dispatcher(state)
    d.dispatch("benchmark create qa")
    d.dispatch('benchmark add-task qa "2+2?" --expected 4 --grader exact')
    result = d.dispatch("benchmark run qa")
    assert isinstance(result[0], Table)  # scorecards rendered, no crash

    # And the score is actually correct (model answered "4", exact-graded vs "4").
    from db.models import Scorecard
    card = session.query(Scorecard).filter_by(model_id="gpt-4o-mini").order_by(Scorecard.created_at.desc()).first()
    assert card.score == 1.0 and card.tasks_passed == 1 and card.tasks_total == 1


def test_benchmark_run_empty_task_set_warns_not_scores(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    from db.models import Scorecard
    d.dispatch("benchmark create empty")
    result = d.dispatch("benchmark run empty")
    assert isinstance(result[0], Text) and "no tasks" in result[0].plain
    assert session.query(Scorecard).count() == 0  # no misleading 0% rows written


def test_benchmark_scorecards_unknown_task_set(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    result = d.dispatch("benchmark scorecards --task-set nobody")
    assert isinstance(result[0], Text) and "not found" in result[0].plain


def test_connect_openai_compatible_without_base_url_errors(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    # is_local is True (no inline-key guard), so it reaches the service, which
    # requires a base_url for openai-compatible and raises a clean error.
    result = d.dispatch("connect openai-compatible")
    assert isinstance(result[0], Text) and "base-url" in result[0].plain.lower()


def test_connect_cloud_with_base_url_no_key_still_prompts(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    # A cloud provider without a key must still be told to supply one, even if a
    # stray --base-url is passed (guard no longer keys off base_url).
    result = d.dispatch("connect openai --base-url http://x")
    assert isinstance(result[0], Text) and "supply the key" in result[0].plain.lower()


def test_route_policy_and_task_set_forwarded(tmp_state, monkeypatch):
    from types import SimpleNamespace
    state, session, home = tmp_state
    captured = {}

    def fake_route_prompt(request, session=None):
        captured["policy"] = request.policy
        captured["task_set"] = request.task_set
        return SimpleNamespace(
            task_type="simple", route_reason="r", provider="openai", model_id="m",
            cache_hit=False, cache_similarity=None, input_tokens=None, output_tokens=None,
            estimated_cost_usd=0.0, latency_ms=None, response_text=None,
            route_explanation="explained",
        )

    monkeypatch.setattr("services.routing_service.route_prompt", fake_route_prompt)
    d = Dispatcher(state)
    d.dispatch('route "hi" --policy benchmarked --task-set qa')
    assert captured == {"policy": "benchmarked", "task_set": "qa"}
