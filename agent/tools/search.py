"""Search under sandbox (ripgrep if available, else naive walk)."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from agent.sandbox import Sandbox, is_sensitive_path
from agent.tool_logging import run_logged

_TEXT_SUFFIXES = {".py", ".toml", ".md", ".txt", ".json", ".yaml", ".yml", ".ini", ".cfg"}
_MAX_FILES_SCAN = 200
_MAX_MATCHES = 50


def search_codebase(
    sandbox: Sandbox,
    query: str,
    *,
    session: Session | None = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    def _do() -> dict[str, Any]:
        if not query.strip():
            return {"ok": False, "error": "empty query", "paths": []}
        rg = shutil.which("rg")
        if rg:
            return _search_ripgrep(sandbox, query, rg)
        return _search_naive(sandbox, query)

    return run_logged(
        "search_codebase",
        _do,
        session=session,
        trace_id=trace_id,
        log_args={"query": query},
    )


def _search_ripgrep(sandbox: Sandbox, query: str, rg: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [rg, "-l", "--fixed-strings", query, str(sandbox.root)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(sandbox.root),
        )
        paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        rel = []
        for p in paths[:_MAX_MATCHES]:
            resolved = Path(p).resolve()
            if is_sensitive_path(resolved, sandbox.root):
                continue  # never surface credential/secret files in search results
            try:
                rel.append(str(resolved.relative_to(sandbox.root)))
            except ValueError:
                continue
        return {
            "ok": proc.returncode in (0, 1),
            "engine": "ripgrep",
            "paths": rel,
            "stderr": proc.stderr[:2000] if proc.stderr else "",
        }
    except Exception as exc:
        return {"ok": False, "engine": "ripgrep", "paths": [], "error": str(exc)}


def _search_naive(sandbox: Sandbox, query: str) -> dict[str, Any]:
    pattern = re.compile(re.escape(query))
    hits: list[str] = []
    scanned = 0
    try:
        for path in sandbox.root.rglob("*"):
            if path.is_file() and path.suffix.lower() in _TEXT_SUFFIXES and not is_sensitive_path(path, sandbox.root):
                scanned += 1
                if scanned > _MAX_FILES_SCAN:
                    break
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    if pattern.search(text):
                        hits.append(str(path.resolve().relative_to(sandbox.root)))
                except OSError:
                    continue
                if len(hits) >= _MAX_MATCHES:
                    break
        return {"ok": True, "engine": "naive", "paths": hits, "files_scanned": scanned}
    except Exception as exc:
        return {"ok": False, "engine": "naive", "paths": [], "error": str(exc)}
