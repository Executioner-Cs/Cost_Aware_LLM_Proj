"""CRUD for model_registry table."""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from db.models import ModelRegistry


def upsert_models(session: Session, models: list[ModelRegistry]) -> None:
    for m in models:
        existing = session.get(ModelRegistry, m.id)
        if existing:
            for attr in ["display_name", "tier", "context_window", "cost_per_1m_input",
                         "cost_per_1m_output", "supports_json", "supports_tools",
                         "supports_vision", "enabled"]:
                setattr(existing, attr, getattr(m, attr))
        else:
            session.add(m)
    session.commit()


def list_enabled(session: Session) -> list[ModelRegistry]:
    return session.query(ModelRegistry).filter_by(enabled=1).all()


def list_for_account(session: Session, account_id: str) -> list[ModelRegistry]:
    return session.query(ModelRegistry).filter_by(account_id=account_id).all()


def get_by_external_id(session: Session, provider: str, external_id: str) -> Optional[ModelRegistry]:
    return (
        session.query(ModelRegistry)
        .filter_by(provider=provider, external_model_id=external_id)
        .first()
    )
