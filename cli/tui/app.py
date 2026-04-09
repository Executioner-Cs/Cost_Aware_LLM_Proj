"""
Orchestrator TUI — Full-screen immersive Textual app.

Layout:
  ┌─────────────────────────────────────────────────┐
  │  ORCHESTRATOR             [status bar]           │  ← Built-in Header + StatusBar widget
  ├─────────────────────────────────────┬───────────┤
  │                                     │  Traces   │
  │         Main Output Panel           │  Cache    │
  │            (RichLog)                │  Accounts │
  │                                     │           │
  ├─────────────────────────────────────┴───────────┤
  │  orchestrator >  ___________________________    │  ← Input bar
  └─────────────────────────────────────────────────┘
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.text import Text
from rich.rule import Rule
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import (
    Header,
    Footer,
    Input,
    Label,
    RichLog,
    Static,
)
from cli.tui.widgets import AccountsWidget


# ── Bootstrap session state ───────────────────────────────────────────────────

@dataclass
class SessionState:
    """Lightweight bootstrap state for pre-TUI status checks and testing.

    The live runtime state (with DB session, full config dict) lives in
    ``cli.tui.dispatcher.SessionState``.  This lighter variant is used by
    ``bootstrap_state()`` and as a fallback when creating the app without a
    real backend (e.g. in tests).
    """
    initialised: bool = False
    provider_count: int = 0
    model_count: int = 0
    cache_enabled: bool = True
    default_quality: str = "balanced"
    quality: str = "balanced"
    cost_this_session: float = 0.0

    def refresh_stats(self) -> None:
        """No-op for the bootstrap variant; the dispatcher's SessionState
        overrides this with real DB queries."""


def bootstrap_state() -> SessionState:
    """Build a quick-check SessionState from disk without opening the TUI.

    Reads ``ORCHESTRATOR_HOME`` (or ``~/.orchestrator``), loads
    ``config.toml`` if present, and optionally counts active providers
    from the SQLite database.
    """
    home = Path(os.environ.get("ORCHESTRATOR_HOME", str(Path.home() / ".orchestrator")))
    state = SessionState()

    if not home.exists():
        return state

    config_path = home / "config.toml"
    if not config_path.exists():
        return state

    state.initialised = True

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        state.cache_enabled = config.get("cache", {}).get("enabled", True)
        state.default_quality = config.get("routing", {}).get("default_quality", "balanced")
        state.quality = state.default_quality
    except Exception:
        pass

    try:
        from db.session import get_session
        session = get_session(home / "orchestrator.db")
        from db.repositories.accounts import list_all
        accounts = list_all(session)
        state.provider_count = len([a for a in accounts if a.status == "active"])
    except Exception:
        pass

    return state


# ── Status bar widget ────────────────────────────────────────────────────────

class StatusBar(Static):
    """Single-line status strip showing providers, cache, quality, session cost."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $primary-darken-3;
        color: $text-muted;
        padding: 0 2;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._providers = 0
        self._cache = True
        self._quality = "balanced"
        self._cost = 0.0

    def update_from_state(self, state) -> None:
        self._providers = state.provider_count
        self._cache = state.cache_enabled
        self._quality = state.quality
        self._cost = state.cost_this_session
        self._render_status()

    def _render_status(self) -> None:
        cache_str = "[green]cache ON[/green]" if self._cache else "[red]cache OFF[/red]"
        self.update(
            f"  [green]providers: {self._providers}[/green]"
            f"   {cache_str}"
            f"   [cyan]quality: {self._quality}[/cyan]"
            f"   [dim]session cost: ${self._cost:.6f}[/dim]"
        )


# ── Side panel widget ────────────────────────────────────────────────────────

class SidePanel(Static):
    """Compact info panel on the right: recent traces + cache stats."""

    DEFAULT_CSS = """
    SidePanel {
        width: 30;
        height: 1fr;
        border-left: tall $primary-darken-2;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]Recent Activity[/bold cyan]\n", id="side-title")
        yield RichLog(id="side-log", wrap=True, markup=True, highlight=False)

    def push(self, text: str) -> None:
        self.query_one("#side-log", RichLog).write(text)


# ── Main Orchestrator App ────────────────────────────────────────────────────

_BANNER_LINES = [
    "  ██████╗ ██████╗  ██████╗██╗  ██╗███████╗███████╗████████╗██████╗  █████╗ ████████╗ ██████╗ ██████╗ ",
    " ██╔═══██╗██╔══██╗██╔════╝██║  ██║██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗",
    " ██║   ██║██████╔╝██║     ███████║█████╗  ███████╗   ██║   ██████╔╝███████║   ██║   ██║   ██║██████╔╝",
    " ██║   ██║██╔══██╗██║     ██╔══██║██╔══╝  ╚════██║   ██║   ██╔══██╗██╔══██║   ██║   ██║   ██║██╔══██╗",
    " ╚██████╔╝██║  ██║╚██████╗██║  ██║███████╗███████║   ██║   ██║  ██║██║  ██║   ██║   ╚██████╔╝██║  ██║",
    "  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝",
]

_BANNER_GRADIENT = (
    "bright_cyan bold",
    "cyan bold",
    "bright_blue bold",
    "blue bold",
    "magenta bold",
    "bright_magenta bold",
)


def _build_welcome_text() -> Text:
    t = Text()
    for i, line in enumerate(_BANNER_LINES):
        t.append(line + "\n", style=_BANNER_GRADIENT[i % len(_BANNER_GRADIENT)])
    t.append("\n")
    t.append("Type ", style="dim")
    t.append("help", style="bold dim")
    t.append(" to see available commands.  Type ", style="dim")
    t.append("quit", style="bold dim")
    t.append(" or press ", style="dim")
    t.append("Ctrl+Q", style="bold dim")
    t.append(" to exit.\n", style="dim")
    return t


class OrchestratorApp(App):
    """Immersive full-screen Textual application."""

    CSS_PATH = "style.tcss"

    TITLE = "Orchestrator"
    SUB_TITLE = "Cost-Aware LLM Router"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_output", "Clear", show=True),
        Binding("escape", "clear_input", "Clear Input", show=False),
        Binding("ctrl+c", "clear_input", "Clear Input", show=False, priority=True),
        Binding("up",     "history_prev", "Prev",  show=False),
        Binding("down",   "history_next", "Next",  show=False),
    ]

    def __init__(self, state=None, dispatcher=None) -> None:
        super().__init__()
        self._state = state or SessionState()
        self._dispatcher = dispatcher
        self._history: list[str] = []
        self._history_pos: int = -1

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatusBar()
        with Horizontal(id="body"):
            with Container(id="output-panel"):
                yield RichLog(id="output", wrap=True, markup=True, highlight=True, auto_scroll=True)
            yield SidePanel()
        with Horizontal(id="input-area"):
            yield Label("[bold cyan]orchestrator >[/bold cyan]  ", id="prompt-label")
            yield Input(placeholder="orchestrator > type a command…", id="cmd-input")
        yield Footer()

    # ── On mount ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._update_status()
        output = self.query_one("#output", RichLog)
        output.write(_build_welcome_text())
        self._write_separator()
        self.query_one("#cmd-input", Input).focus()

    # ── Input submitted ───────────────────────────────────────────────────────

    @on(Input.Submitted, "#cmd-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        inp = self.query_one("#cmd-input", Input)
        inp.value = ""

        if not raw:
            return

        # History
        if not self._history or self._history[-1] != raw:
            self._history.append(raw)
        self._history_pos = -1

        output = self.query_one("#output", RichLog)
        output.write(f"[bold cyan]orchestrator >[/bold cyan]  [bold]{raw}[/bold]")

        if self._dispatcher is None:
            output.write(Text("Dispatcher not available.", style="dim"))
            return

        # Dispatch
        try:
            results = self._dispatcher.dispatch(raw)
        except Exception as exc:
            output.write(Text(f"Internal error: {exc}", style="bold red"))
            return

        has_widget = False
        for item in results:
            if item == "__quit__":
                self.exit()
                return
            elif item == "__clear__":
                output.clear()
                # Also remove any mounted interactive widgets
                for w in self.query(AccountsWidget):
                    w.remove()
                self._write_separator()
                return
            elif isinstance(item, Widget):
                # Mount interactive widget inside the output panel
                output_panel = self.query_one("#output-panel", Container)
                self.mount(item, before=output_panel.query_one("#output", RichLog))
                has_widget = True
            else:
                output.write(item)

        self._write_separator()
        self._update_status()

        # Mirror key commands to side panel
        side = self.query_one(SidePanel)
        if raw.startswith("route"):
            side.push(f"[dim]route[/dim] {raw[5:50]}")

    # ── Widget messages ───────────────────────────────────────────────────────

    def on_accounts_widget_disconnected(self, event: AccountsWidget.Disconnected) -> None:
        """Refresh status bar whenever an account is disconnected via the widget."""
        self._update_status()
        # Return focus to input
        self.query_one("#cmd-input", Input).focus()

    # ── Key bindings ─────────────────────────────────────────────────────────

    def action_clear_input(self) -> None:
        self.query_one("#cmd-input", Input).value = ""

    def action_clear_output(self) -> None:
        for w in self.query(AccountsWidget):
            w.remove()
        output = self.query_one("#output", RichLog)
        output.clear()
        self._write_separator()

    def action_history_prev(self) -> None:
        if not self._history:
            return
        if self._history_pos == -1:
            self._history_pos = len(self._history) - 1
        elif self._history_pos > 0:
            self._history_pos -= 1
        inp = self.query_one("#cmd-input", Input)
        inp.value = self._history[self._history_pos]
        inp.cursor_position = len(inp.value)

    def action_history_next(self) -> None:
        if self._history_pos == -1:
            return
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            self.query_one("#cmd-input", Input).value = self._history[self._history_pos]
        else:
            self._history_pos = -1
            self.query_one("#cmd-input", Input).value = ""

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _update_status(self) -> None:
        self._state.refresh_stats()
        self.query_one(StatusBar).update_from_state(self._state)
        self.sub_title = (
            f"providers: {self._state.provider_count}  "
            f"models: {getattr(self._state, 'model_count', 0)}  "
            f"{'cache ON' if self._state.cache_enabled else 'cache OFF'}  "
            f"quality: {self._state.quality}"
        )

    def _write_separator(self) -> None:
        self.query_one("#output", RichLog).write(Rule(style="dim"))


# ── Factory ──────────────────────────────────────────────────────────────────

def create_app() -> OrchestratorApp:
    """Bootstrap session state and return a ready-to-run OrchestratorApp."""
    from services.init_service import get_home, load_config
    from db.session import get_session, create_all_tables

    home = get_home()

    # Auto-init if not set up yet
    if not (home / "orchestrator.db").exists():
        from services.init_service import run_init
        run_init(home)

    config = load_config(home)
    db_path = home / "orchestrator.db"
    create_all_tables(db_path)
    session = get_session(db_path)

    from cli.tui.dispatcher import SessionState, Dispatcher

    state = SessionState(session=session, home=home, config=config)
    state.refresh_stats()

    dispatcher = Dispatcher(state)
    return OrchestratorApp(state, dispatcher)
