"""Execute model-proposed tool calls against sandboxed implementations."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from agent.sandbox import Sandbox
from agent.tools import execution, file_io, search


def dispatch_tool(
    name: str,
    arguments_json: str,
    *,
    sandbox: Sandbox,
    session: Session | None = None,
    trace_id: Optional[str] = None,
    allow_shell: bool = False,
    subprocess_timeout_sec: float = 60.0,
    blocked_shell_patterns: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Parse JSON arguments and run the named tool. Returns a structured dict (never raises for bad JSON)."""
    try:
        args: dict[str, Any] = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid tool arguments JSON: {exc}"}

    if name == "read_file":
        path = args.get("path", "")
        return file_io.read_file(sandbox, str(path), session=session, trace_id=trace_id)
    if name == "write_file":
        return file_io.write_file(
            sandbox,
            str(args.get("path", "")),
            str(args.get("content", "")),
            session=session,
            trace_id=trace_id,
        )
    if name == "list_dir":
        d = args.get("directory", ".")
        return file_io.list_dir(sandbox, str(d), session=session, trace_id=trace_id)
    if name == "search_codebase":
        return search.search_codebase(
            sandbox,
            str(args.get("query", "")),
            session=session,
            trace_id=trace_id,
        )
    if name == "run_python":
        return execution.run_python(
            sandbox,
            str(args.get("code", "")),
            timeout_sec=min(subprocess_timeout_sec, 120.0),
            session=session,
            trace_id=trace_id,
        )
    if name == "run_shell":
        return execution.run_shell(
            sandbox,
            str(args.get("command", "")),
            allow_shell=allow_shell,
            blocked_shell_patterns=blocked_shell_patterns,
            timeout_sec=min(subprocess_timeout_sec, 120.0),
            session=session,
            trace_id=trace_id,
        )
    if name == "run_tests":
        return execution.run_tests(
            sandbox,
            timeout_sec=min(subprocess_timeout_sec, 300.0),
            session=session,
            trace_id=trace_id,
        )
    return {"ok": False, "error": f"unknown tool: {name}"}
