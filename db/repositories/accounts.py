"""CRUD for connected_accounts table."""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from db.models import ConnectedAccount


def create(session: Session, account: ConnectedAccount) -> ConnectedAccount:
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def get_by_id(session: Session, account_id: str) -> Optional[ConnectedAccount]:
    return session.get(ConnectedAccount, account_id)


def get_by_provider(session: Session, provider: str) -> list[ConnectedAccount]:
    return session.query(ConnectedAccount).filter_by(provider=provider, status="active").all()


def list_all(session: Session) -> list[ConnectedAccount]:
    return session.query(ConnectedAccount).all()


def update(session: Session, account: ConnectedAccount) -> ConnectedAccount:
    session.commit()
    session.refresh(account)
    return account


def delete(session: Session, account: ConnectedAccount) -> None:
    session.delete(account)
    session.commit()
