"""
Reusable interactive Textual widgets for the Orchestrator TUI.
"""
from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.widgets import Button, DataTable, Label, Static
from textual.containers import Horizontal, Vertical
from textual.message import Message


class AccountsWidget(Static):
    """
    Interactive accounts table with a clickable Disconnect button.

    Shows full connected_at timestamp and a [Disconnect] button that
    operates on the currently highlighted row.
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("d", "disconnect_selected", "Disconnect", show=True),
    ]

    # Posted when an account is successfully disconnected so the app can
    # refresh its status bar.
    class Disconnected(Message):
        def __init__(self, account_id: str) -> None:
            super().__init__()
            self.account_id = account_id

    DEFAULT_CSS = """
    AccountsWidget {
        height: auto;
        border: round cyan;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    AccountsWidget #accounts-title {
        color: $text;
        text-style: bold;
        padding: 0 1;
    }
    AccountsWidget DataTable {
        height: auto;
        max-height: 14;
    }
    AccountsWidget #accounts-footer {
        height: 1;
        margin-top: 1;
    }
    AccountsWidget #btn-disconnect {
        margin: 0 2;
    }
    """

    def __init__(
        self,
        accounts: list,
        session,
        on_disconnect: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._accounts = list(accounts)
        self._session = session
        self._on_disconnect = on_disconnect

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Label(
            f"[bold cyan]Connected Accounts[/bold cyan]  [dim]({len(self._accounts)} total)[/dim]"
            "   [dim]↑↓ Navigate   D / button to disconnect   Esc Close[/dim]",
            id="accounts-title",
        )
        yield DataTable(id="accounts-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="accounts-footer"):
            yield Button("Disconnect Selected", variant="error", id="btn-disconnect")

    def on_mount(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        table.add_column("ID", width=16)
        table.add_column("Provider", width=10)
        table.add_column("Name", width=20)
        table.add_column("Connected At", width=20)
        table.add_column("Status", width=8)
        for a in self._accounts:
            connected_at = (a.connected_at or "—")[:19].replace("T", " ")
            table.add_row(
                a.id[:14] + "…",
                a.provider,
                (a.display_name or "—")[:20],
                connected_at,
                a.status,
                key=a.id,  # full UUID as row key for remove_row()
            )
        if self._accounts:
            table.focus()

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_close(self) -> None:
        self.remove()

    def action_disconnect_selected(self) -> None:
        self._do_disconnect()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-disconnect":
            self._do_disconnect()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _do_disconnect(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._accounts):
            return

        account = self._accounts[row_idx]
        account_id = account.id

        try:
            from services.account_service import disconnect_account
            disconnect_account(self._session, account_id)
        except Exception as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        # Remove from local list and table (key=account_id was set in add_row)
        self._accounts.pop(row_idx)
        table.remove_row(account_id)

        self.notify(
            f"Disconnected {account.provider} account {account_id[:8]}…",
            severity="information",
            timeout=3,
        )
        self.post_message(self.Disconnected(account_id))

        if self._on_disconnect:
            self._on_disconnect(account_id)

        # Auto-close if no accounts remain
        if not self._accounts:
            self.remove()
