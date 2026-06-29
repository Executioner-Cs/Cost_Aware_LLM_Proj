"""
orchestrator init: sets up the ~/.orchestrator directory, config, and SQLite
tables. The default exact cache needs no vector store or embedding model, so
init no longer provisions Qdrant or warms an embedder.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

from db.session import get_session
from db.session import create_all_tables
from services.connect_service import connect as svc_connect
from utils.console import console, print_error, print_success, print_warning
from utils.env import get_provider_api_key, load_dotenv_once
from utils.setup_interactive import get_interactive_status, pick_provider
from utils.setup_ui import render_init_banner, render_init_handoff_panel, render_init_success_panel


DEFAULT_CONFIG = """\
[routing]
default_quality = "balanced"
prefer_cheapest = true
fallback_enabled = true

[cache]
enabled = true
# mode: "exact" (default, no extra deps) | "off"
# Semantic cache v1 was removed; a lighter semantic cache returns in semantic-cache-v2.
mode = "exact"
ttl_seconds = 86400

[cost]
warn_above_usd = 0.01
monthly_budget_usd = 0

[display]
show_cost = true
show_tokens = true
show_route_reason = true
show_cache_similarity = true

[agent]
# Sandbox root for agent tools (paths resolved relative to cwd if relative).
sandbox_root = "."
max_iterations = 8
max_file_bytes = 1048576
max_subprocess_seconds = 120
# run_python and run_shell are arbitrary code execution. Both are disabled by
# default and are not even offered to the model unless enabled here.
allow_python = false
allow_shell = false
# Comma-separated substrings; shell commands containing any are rejected.
blocked_shell_patterns = "rm -rf,mkfs,dd if=,:(){:|:&};:"
# Advisory only: true OS-level network isolation is NOT enforced for tool
# subprocesses. Do not treat this as a security boundary.
network_disabled = true
"""


def get_home() -> Path:
    return Path(os.environ.get("ORCHESTRATOR_HOME", Path.home() / ".orchestrator"))


def run_init(home: Path | None = None) -> None:
    if home is None:
        home = get_home()

    render_init_banner()
    home.mkdir(parents=True, exist_ok=True)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as progress:

        # 1. Write default config if absent
        t = progress.add_task("Writing config.toml…")
        config_path = home / "config.toml"
        if not config_path.exists():
            config_path.write_text(DEFAULT_CONFIG)
        progress.update(t, completed=True)

        # 2. Create SQLite tables. The default exact cache provisions its own
        #    table lazily on first use and needs no vector store or embedder.
        progress.update(t, description="Creating SQLite tables…")
        db_path = home / "orchestrator.db"
        create_all_tables(db_path)
        progress.update(t, completed=True)

    print_success(f"Orchestrator initialised at [bold]{home}[/bold]")
    render_init_success_panel(home)


def _run_post_init_connect_handoff() -> None:
    status = get_interactive_status(console)
    if not status.can_prompt:
        _print_fallback_connect_commands(status.message)
        return

    render_init_handoff_panel()
    load_dotenv_once()

    provider = pick_provider(console)
    if not provider:
        _print_fallback_connect_commands("No provider selected.")
        return

    # Prefer an env / .env key; otherwise prompt. Either way a connect attempt
    # may retry on a bad key, then fall back to manual commands. Single provider
    # per init handoff; the picker terminates the flow.
    env_key = (get_provider_api_key(provider) or "").strip()
    if env_key:
        account_id, display_name = _try_connect(provider, env_key)
        if account_id:
            _print_connect_success(provider, account_id, display_name)
            return
        print_warning(f"Saved {provider} key failed. Enter a valid key to retry.")
        if _prompt_loop_until_connected(provider):
            return
        _print_fallback_connect_commands("No API key supplied.")
        return

    key = _prompt_api_key(provider)
    if not key:
        _print_fallback_connect_commands("No API key supplied.")
        return
    account_id, display_name = _try_connect(provider, key)
    if account_id:
        _print_connect_success(provider, account_id, display_name)
        return
    print_warning("Connect failed. Enter a valid key to retry, or submit empty to skip.")
    if _prompt_loop_until_connected(provider):
        return
    _print_fallback_connect_commands("No API key supplied.")


def _prompt_api_key(provider: str) -> str:
    try:
        return Prompt.ask(f"Enter {provider} API key", password=False, default="").strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def _prompt_loop_until_connected(provider: str, connected: list[str] | None = None) -> bool:
    """
    Visible-input retry loop: keep asking for key until success or empty input.
    Appends provider to `connected` on success.
    """
    while True:
        key = _prompt_api_key(provider)
        if not key:
            return False
        account_id, display_name = _try_connect(provider, key)
        if account_id:
            _print_connect_success(provider, account_id, display_name)
            if connected is not None:
                connected.append(provider)
            return True
        print_warning("Invalid key. Try again or submit empty input to return to picker.")


def _try_connect(provider: str, key: str) -> tuple[str, str]:
    """Attempt a single connect call. Returns (account_id, display_name) or ("", "")."""
    session = None
    try:
        with console.status(f"[cyan]Connecting to {provider}..."):
            session = get_session()
            account = svc_connect(session, provider, key)
            return account.id, account.display_name or ""
    except ValueError as exc:
        print_error(str(exc))
        return "", ""
    except Exception as exc:
        print_error(f"Unexpected error: {exc}")
        return "", ""
    finally:
        if session is not None:
            session.close()


def _print_connect_success(provider: str, account_id: str, display_name: str) -> None:
    print_success(
        f"Connected [bold]{provider}[/bold] account "
        f"[dim]{display_name or ''}[/dim] (id: {account_id[:8]}...)"
    )


def _print_fallback_connect_commands(reason: str) -> None:
    print_warning(reason)
    console.print("[bold bright_cyan]Manual next steps:[/bold bright_cyan]")
    for provider in ("openai", "anthropic", "gemini", "groq"):
        console.print(f"[cyan]- orchestrator connect {provider}[/cyan]")
    console.print("[cyan]- orchestrator model list[/cyan]")
    console.print('[cyan]- orchestrator route "Summarize this text"[/cyan]')


def load_config(home: Path | None = None) -> dict:
    if home is None:
        home = get_home()
    config_path = home / "config.toml"
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)
