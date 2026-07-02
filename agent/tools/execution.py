"""Run Python, shell (optional), or pytest inside sandbox with timeouts."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from agent.sandbox import Sandbox
from agent.tool_logging import run_logged


# Allowlist of environment variables forwarded to agent subprocesses. An
# allowlist (not a denylist) guarantees no provider key, token, or credential
# can leak in, regardless of what the parent process environment contains.
_SAFE_ENV_KEYS = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SystemRoot", "WINDIR", "windir",
    "TEMP", "TMP", "TMPDIR", "COMSPEC", "NUMBER_OF_PROCESSORS",
    "PYTHONPATH", "PYTHONIOENCODING", "PYTHONHOME",
    "LANG", "LC_ALL", "LC_CTYPE",
)


def _safe_subprocess_env() -> dict[str, str]:
    """Minimal, secret-free environment for agent subprocesses.

    Only safe basics are forwarded. Provider API keys, ORCHESTRATOR_KEY_FILE,
    and anything matching *_API_KEY / *_TOKEN / *_SECRET / *_PASSWORD /
    *_CREDENTIAL* cannot reach a tool subprocess: they are not on the allowlist.
    """
    env = {k: os.environ[k] for k in _SAFE_ENV_KEYS if k in os.environ}
    if "PATH" not in env:
        env["PATH"] = os.defpath
    return env


def run_python(
    sandbox: Sandbox,
    code: str,
    *,
    enabled: bool = False,
    timeout_sec: float = 30.0,
    session: Session | None = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    def _do() -> dict[str, Any]:
        if not enabled:
            return {
                "ok": False,
                "error": "run_python is disabled. Enable it in agent config ([agent] allow_python = true) to run Python in the sandbox.",
                "stdout": "",
                "stderr": "",
            }
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(sandbox.root),
                env=_safe_subprocess_env(),
            )
            return {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout", "stdout": "", "stderr": ""}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "stdout": "", "stderr": ""}

    return run_logged(
        "run_python",
        _do,
        session=session,
        trace_id=trace_id,
        log_args={"code_len": len(code)},
    )


def _shell_blocked(command: str, patterns: list[str] | None) -> str | None:
    if not patterns:
        return None
    low = command.lower()
    for p in patterns:
        if p and p.lower() in low:
            return f"command matched blocked pattern: {p!r}"
    return None


def run_shell(
    sandbox: Sandbox,
    command: str,
    *,
    allow_shell: bool = False,
    blocked_shell_patterns: list[str] | None = None,
    timeout_sec: float = 30.0,
    session: Session | None = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    def _do() -> dict[str, Any]:
        if not allow_shell:
            return {
                "ok": False,
                "error": "shell execution disabled (set allow_shell in agent config)",
                "stdout": "",
                "stderr": "",
            }
        blocked = _shell_blocked(command, blocked_shell_patterns)
        if blocked:
            return {"ok": False, "error": blocked, "stdout": "", "stderr": ""}
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(sandbox.root),
                env=_safe_subprocess_env(),
            )
            return {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout", "stdout": "", "stderr": ""}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "stdout": "", "stderr": ""}

    return run_logged(
        "run_shell",
        _do,
        session=session,
        trace_id=trace_id,
        log_args={"command": command},
    )


def run_tests(
    sandbox: Sandbox,
    *,
    timeout_sec: float = 120.0,
    session: Session | None = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    def _do() -> dict[str, Any]:
        pytest_exe = Path(sys.executable).parent / "pytest"
        cmd = [str(pytest_exe), "-q"] if pytest_exe.exists() else [sys.executable, "-m", "pytest", "-q"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(sandbox.root),
                env=_safe_subprocess_env(),
            )
            return {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout", "stdout": "", "stderr": ""}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "stdout": "", "stderr": ""}

    return run_logged(
        "run_tests",
        _do,
        session=session,
        trace_id=trace_id,
        log_args={},
    )
