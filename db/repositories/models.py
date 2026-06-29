"""CRUD for model_registry table."""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from db.models import ModelRegistry


# Metadata refreshed on re-sync. The logical identity (provider,
# external_model_id) and the surrogate id / account_id are NOT in this list.
_MUTABLE_FIELDS = (
    "display_name", "tier", "context_window", "cost_per_1m_input",
    "cost_per_1m_output", "supports_json", "supports_tools",
    "supports_vision", "enabled",
)


def upsert_models(session: Session, models: list[ModelRegistry]) -> None:
    """Insert or update models keyed on the stable logical identity
    (provider, external_model_id), NOT the surrogate UUID ``id``.

    Each sync builds rows with fresh UUIDs; keying the lookup on the UUID (as the
    old code did) always missed and inserted, so re-syncing a provider duplicated
    every model. Keying on (provider, external_model_id) makes sync idempotent:
    a matching row is updated in place. The existing row's ``id`` and
    ``account_id`` are preserved so foreign keys and cascade deletes stay intact.
    """
    for m in models:
        existing = get_by_external_id(session, m.provider, m.external_model_id)
        if existing is not None:
            for attr in _MUTABLE_FIELDS:
                setattr(existing, attr, getattr(m, attr))
        else:
            session.add(m)
    session.commit()


def list_enabled(session: Session) -> list[ModelRegistry]:
    """Enabled models, deduplicated by stable identity (provider, external_model_id).

    Collapsing here keeps routing candidates and ``model list`` free of any
    pre-existing duplicate rows (created before sync was idempotent) without
    deleting user data. The earliest-discovered row per identity wins.
    """
    rows = (
        session.query(ModelRegistry)
        .filter_by(enabled=1)
        .order_by(
            ModelRegistry.provider,
            ModelRegistry.external_model_id,
            ModelRegistry.discovered_at,
        )
        .all()
    )
    seen: set[tuple[str, str]] = set()
    unique: list[ModelRegistry] = []
    for m in rows:
        key = (m.provider, m.external_model_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)
    return unique


def list_for_account(session: Session, account_id: str) -> list[ModelRegistry]:
    return session.query(ModelRegistry).filter_by(account_id=account_id).all()


def get_by_external_id(session: Session, provider: str, external_id: str) -> Optional[ModelRegistry]:
    return (
        session.query(ModelRegistry)
        .filter_by(provider=provider, external_model_id=external_id)
        .first()
    )
