"""Load [agent] section from orchestrator config.toml with safe defaults."""
from __future__ import annotations

from pathlib import Path

from services.init_service import get_home, load_config


# Case-insensitive substrings refused in run_shell commands. Destructive ops plus
# curl/wget (advisory network defense, since network_disabled is not enforced).
# Users can override the whole list via [agent].blocked_shell_patterns in config.
_DEFAULT_BLOCKED_SHELL_PATTERNS = [
    "rm -rf", "mkfs", "dd if=", ":(){:|:&};:",
    "chmod -R", "chown -R", "sudo ", "shutdown", "reboot", "> /dev/",
    "curl ", "wget ",
]


def _parse_blocked_patterns(raw: str | None) -> list[str]:
    if not raw:
        return list(_DEFAULT_BLOCKED_SHELL_PATTERNS)
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def load_agent_config(home: Path | None = None) -> dict:
    h = home or get_home()
    cfg = load_config(h)
    raw = cfg.get("agent") or {}
    return {
        "sandbox_root": str(raw.get("sandbox_root", ".")),
        "max_iterations": int(raw.get("max_iterations", 8)),
        "max_file_bytes": int(raw.get("max_file_bytes", 1_048_576)),
        "max_subprocess_seconds": float(raw.get("max_subprocess_seconds", 120)),
        "allow_shell": bool(raw.get("allow_shell", False)),
        "allow_python": bool(raw.get("allow_python", False)),
        "blocked_shell_patterns": _parse_blocked_patterns(raw.get("blocked_shell_patterns")),
        # Advisory only: network access is NOT enforced for tool subprocesses.
        # Do not present this as a hard isolation boundary.
        "network_disabled": bool(raw.get("network_disabled", True)),
    }
