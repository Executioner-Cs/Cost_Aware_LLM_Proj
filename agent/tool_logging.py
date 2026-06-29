"""Persist tool invocations to SQLite."""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from db.models import ToolCall
from db.repositories.tool_calls import create as create_tool_call

_REDACTED = "***REDACTED***"
# Keys whose values are secret regardless of content.
_SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|credential|key_file)", re.IGNORECASE)
# Provider key shapes that may appear inside free-form strings (e.g. a shell command).
_SECRET_VALUE_RE = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{6,}|sk-[A-Za-z0-9_-]{6,}|gsk_[A-Za-z0-9]{6,}|AIza[A-Za-z0-9_-]{10,})"
)
# NAME=value / NAME: value where NAME looks key-like (e.g. OPENAI_API_KEY=...).
_ASSIGN_RE = re.compile(
    r"([A-Za-z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL[A-Z]*))(\s*[=:]\s*)(\S+)",
    re.IGNORECASE,
)


def _redact_str(s: str) -> str:
    s = _ASSIGN_RE.sub(lambda m: m.group(1) + m.group(2) + _REDACTED, s)
    s = _SECRET_VALUE_RE.sub(_REDACTED, s)
    return s


def redact(obj: Any) -> Any:
    """Recursively redact secret-looking keys and values before persistence."""
    if isinstance(obj, dict):
        return {
            k: (_REDACTED if isinstance(k, str) and _SECRET_KEY_RE.search(k) else redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        return _redact_str(obj)
    return obj


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
        args_json=json.dumps(redact(args), default=str),
        result_json=json.dumps(redact(result), default=str),
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
