"""CRUD for traces table."""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from db.models import Trace


def create(session: Session, trace: Trace) -> Trace:
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return trace


def get_by_id(session: Session, trace_id: str) -> Optional[Trace]:
    return session.get(Trace, trace_id)


def list_recent(session: Session, limit: int = 20) -> list[Trace]:
    return (
        session.query(Trace)
        .order_by(Trace.created_at.desc())
        .limit(limit)
        .all()
    )
