"""CRUD for tool_calls table."""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.models import ToolCall


def create(session: Session, row: ToolCall) -> ToolCall:
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
