"""
Model registry integrity: sync must be idempotent and the candidate pool must
never contain duplicate (provider, external_model_id) identities.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ModelRegistry
from db.repositories.models import upsert_models, list_enabled, get_by_external_id


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reg.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _model(provider, ext_id, *, account_id="acc-1", cost_in=1.0, tier="small", display=None):
    return ModelRegistry(
        id=str(uuid.uuid4()),  # fresh UUID every build, exactly like provider sync does
        account_id=account_id,
        provider=provider,
        external_model_id=ext_id,
        display_name=display or ext_id,
        tier=tier,
        context_window=128_000,
        cost_per_1m_input=cost_in,
        cost_per_1m_output=cost_in * 2,
        supports_json=1,
        supports_tools=1,
        supports_vision=0,
        enabled=1,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )


def _raw_count(session, provider, ext_id):
    return session.query(ModelRegistry).filter_by(provider=provider, external_model_id=ext_id).count()


def test_sync_twice_creates_no_duplicate_models(session):
    upsert_models(session, [_model("openai", "gpt-4o-mini"), _model("openai", "gpt-4o")])
    upsert_models(session, [_model("openai", "gpt-4o-mini"), _model("openai", "gpt-4o")])
    assert _raw_count(session, "openai", "gpt-4o-mini") == 1
    assert _raw_count(session, "openai", "gpt-4o") == 1
    assert session.query(ModelRegistry).count() == 2


def test_resync_updates_existing_row_in_place(session):
    upsert_models(session, [_model("openai", "gpt-4o-mini", cost_in=1.0, tier="small")])
    original_id = get_by_external_id(session, "openai", "gpt-4o-mini").id

    changed = _model("openai", "gpt-4o-mini", cost_in=5.0, tier="balanced")
    changed.supports_vision = 1
    upsert_models(session, [changed])

    row = get_by_external_id(session, "openai", "gpt-4o-mini")
    assert session.query(ModelRegistry).count() == 1
    assert row.id == original_id          # surrogate id preserved (stable across sessions)
    assert row.cost_per_1m_input == 5.0   # pricing refreshed
    assert row.tier == "balanced"
    assert row.supports_vision == 1


def test_resync_preserves_account_id_and_does_not_duplicate(session):
    upsert_models(session, [_model("openai", "gpt-4o-mini", account_id="acc-1")])
    # A later connect rebuilds the same model under a different (duplicate) account.
    upsert_models(session, [_model("openai", "gpt-4o-mini", account_id="acc-2")])
    rows = session.query(ModelRegistry).filter_by(provider="openai", external_model_id="gpt-4o-mini").all()
    assert len(rows) == 1
    assert rows[0].account_id == "acc-1"  # ownership preserved; no duplicate row


def test_list_enabled_collapses_preexisting_duplicates(session):
    # A dirty DB created before sync was idempotent: two raw rows, same identity.
    session.add(_model("openai", "gpt-4o-mini"))
    session.add(_model("openai", "gpt-4o-mini"))
    session.commit()
    assert session.query(ModelRegistry).count() == 2  # rows are NOT auto-deleted

    enabled = list_enabled(session)
    keys = [(m.provider, m.external_model_id) for m in enabled]
    assert keys.count(("openai", "gpt-4o-mini")) == 1  # collapsed for routing/listing


def test_candidate_pool_has_no_duplicate_identities(session):
    session.add_all([
        _model("openai", "gpt-4o-mini"),
        _model("openai", "gpt-4o-mini"),
        _model("anthropic", "claude-haiku"),
    ])
    session.commit()
    keys = [(m.provider, m.external_model_id) for m in list_enabled(session)]
    assert len(keys) == len(set(keys))


def test_existing_duplicates_not_made_worse(session):
    session.add_all([_model("openai", "gpt-4o-mini"), _model("openai", "gpt-4o-mini")])
    session.commit()
    before = session.query(ModelRegistry).count()
    upsert_models(session, [_model("openai", "gpt-4o-mini")])  # re-sync over the dupes
    after = session.query(ModelRegistry).count()
    assert after == before  # updated an existing row, inserted nothing, deleted nothing


def test_no_db_unique_constraint_create_all_myth():
    # We deliberately do NOT add a DB unique constraint: create_all cannot add one
    # to an existing user DB without a migration framework. Idempotency lives in the
    # repository layer instead.
    cols = {c.name for c in ModelRegistry.__table__.columns}
    assert {"provider", "external_model_id"} <= cols
    uniques = [c for c in ModelRegistry.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert uniques == []
