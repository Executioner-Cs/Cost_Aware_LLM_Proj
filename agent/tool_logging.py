"""Persist tool invocations to SQLite."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from db.models import ToolCall
from db.repositories.tool_calls import create as create_tool_call


def log_tool_call(
    session: Session | None,
    name: str,
    args: dict[str, Any],
    result: dict[str, Any],
    duration_ms: int,
    trace_id: Optional[str] = None,
) -> None:
    if session is None:
        return
    row = ToolCall(
        id=str(uuid.uuid4()),
        trace_id=trace_id,
        name=name,
        args_json=json.dumps(args, default=str),
        result_json=json.dumps(result, default=str),
        duration_ms=duration_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    create_tool_call(session, row)


def run_logged(
    name: str,
    fn: Callable[[], dict[str, Any]],
    *,
    session: Session | None = None,
    trace_id: Optional[str] = None,
    log_args: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    t0 = time.monotonic()
    result = fn()
    duration_ms = int((time.monotonic() - t0) * 1000)
    log_tool_call(
        session,
        name,
        log_args or {},
        result,
        duration_ms,
        trace_id=trace_id,
    )
    return result
