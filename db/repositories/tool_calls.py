"""CRUD for tool_calls table."""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from db.models import ToolCall


def create(session: Session, tool_call: ToolCall) -> ToolCall:
    session.add(tool_call)
    session.commit()
    session.refresh(tool_call)
    return tool_call


def list_for_trace(session: Session, trace_id: str) -> list[ToolCall]:
    return (
        session.query(ToolCall)
        .filter_by(trace_id=trace_id)
        .order_by(ToolCall.created_at.asc())
        .all()
    )


def get_by_id(session: Session, tool_call_id: str) -> Optional[ToolCall]:
    return session.get(ToolCall, tool_call_id)
