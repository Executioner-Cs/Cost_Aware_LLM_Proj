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


def test_cache_stats_no_qdrant(tmp_state):
    state, session, home = tmp_path = tmp_state
    d = Dispatcher(state)
    # Qdrant not initialised yet — should return error text, not crash
    result = d.dispatch("cache stats")
    assert len(result) >= 1


def test_route_no_models_returns_error(tmp_state):
    state, session, home = tmp_state
    d = Dispatcher(state)
    from rich.text import Text
    result = d.dispatch('route "hello world"')
    # Should return error text (no models in DB)
    assert any(isinstance(r, Text) for r in result)
