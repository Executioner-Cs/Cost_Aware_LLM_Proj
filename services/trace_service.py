"""Service for trace retrieval."""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.models import Trace
from db.repositories.traces import list_recent, get_by_id


def get_traces(session: Session, limit: int = 20) -> list[Trace]:
    return list_recent(session, limit)


def get_trace(session: Session, trace_id: str) -> Trace | None:
    return get_by_id(session, trace_id)
