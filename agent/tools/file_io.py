"""Sandboxed file I/O tools returning structured JSON-friendly dicts."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from agent.sandbox import Sandbox
from agent.tool_logging import run_logged


def read_file(
    sandbox: Sandbox,
    path: str,
    *,
    session: Session | None = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    def _do() -> dict[str, Any]:
        try:
            p = sandbox.resolve_path(path)
            if not p.is_file():
                return {"ok": False, "path": path, "error": "not a file"}
            size = p.stat().st_size
            if size > sandbox.max_file_bytes:
                return {
                    "ok": False,
                    "path": path,
                    "error": f"file too large ({size} > {sandbox.max_file_bytes})",
                }
            return {"ok": True, "path": str(p), "content": p.read_text(encoding="utf-8", errors="replace")}
        except Exception as exc:
            return {"ok": False, "path": path, "error": str(exc)}

    return run_logged(
        "read_file",
        _do,
        session=session,
        trace_id=trace_id,
        log_args={"path": path},
    )


def write_file(
    sandbox: Sandbox,
    path: str,
    content: str,
    *,
    overwrite: bool = False,
    session: Session | None = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    def _do() -> dict[str, Any]:
        try:
            if len(content.encode("utf-8")) > sandbox.max_file_bytes:
                return {"ok": False, "path": path, "error": "content exceeds max_file_bytes"}
            p = sandbox.resolve_path(path)
            # In agent mode, refuse to clobber an existing file unless the caller
            # explicitly opts in. New files write freely.
            if p.exists() and not overwrite:
                return {
                    "ok": False,
                    "path": str(p),
                    "error": "file exists; refusing to overwrite (pass overwrite=true to replace it)",
                }
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"ok": True, "path": str(p), "bytes_written": len(content.encode("utf-8"))}
        except Exception as exc:
            return {"ok": False, "path": path, "error": str(exc)}

    return run_logged(
        "write_file",
        _do,
        session=session,
        trace_id=trace_id,
        log_args={"path": path, "content_len": len(content), "overwrite": overwrite},
    )


def list_dir(
    sandbox: Sandbox,
    directory: str = ".",
    *,
    session: Session | None = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    def _do() -> dict[str, Any]:
        try:
            p = sandbox.resolve_path(directory)
            if not p.is_dir():
                return {"ok": False, "directory": directory, "error": "not a directory"}
            names = sorted([x.name for x in p.iterdir()])
            return {"ok": True, "directory": str(p), "entries": names}
        except Exception as exc:
            return {"ok": False, "directory": directory, "error": str(exc)}

    return run_logged(
        "list_dir",
        _do,
        session=session,
        trace_id=trace_id,
        log_args={"directory": directory},
    )
