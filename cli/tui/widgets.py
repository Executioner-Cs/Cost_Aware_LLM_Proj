"""
Reusable interactive Textual widgets for the Orchestrator TUI.
"""
from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, DataTable, Label, Static
from textual.containers import Horizontal
from textual.message import Message


class AccountsWidget(Static):
    """
    Interactive accounts table with Kill Account and View ID buttons.

    - ↑↓  Navigate rows
    - D / [Kill Account]  Disconnect the selected account
    - V / [View ID]       Show the full UUID of the selected account
    - Esc                 Dismiss the widget
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("d", "disconnect_selected", "Kill Account", show=True),
        Binding("v", "view_id", "View ID", show=True),
    ]

    class Disconnected(Message):
        def __init__(self, account_id: str) -> None:
            super().__init__()
            self.account_id = account_id

    DEFAULT_CSS = """
    AccountsWidget {
        height: auto;
        border: round cyan;
        margin: 0 0 1 0;
        padding: 0 1 1 1;
    }
    AccountsWidget #accounts-title {
        color: $text;
        text-style: bold;
        padding: 0 0 1 0;
        height: 2;
    }
    AccountsWidget DataTable {
        height: auto;
        max-height: 14;
    }
    AccountsWidget #accounts-footer {
        height: 3;
        margin-top: 1;
        align: left middle;
    }
    AccountsWidget #btn-kill {
        min-width: 16;
        margin-right: 2;
    }
    AccountsWidget #btn-view-id {
        min-width: 12;
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
        count = len(self._accounts)
        yield Label(
            f"[bold cyan]Connected Accounts[/bold cyan]  [dim]({count} total)"
            "   ↑↓ Navigate   D Kill Account   V View ID   Esc Close[/dim]",
            id="accounts-title",
        )
        yield DataTable(id="accounts-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="accounts-footer"):
            yield Button("Kill Account", variant="error",   id="btn-kill")
            yield Button("View ID",      variant="default", id="btn-view-id")

    def on_mount(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        table.add_column("ID",           width=16)
        table.add_column("Provider",     width=10)
        table.add_column("Name",         width=22)
        table.add_column("Connected At", width=20)
        table.add_column("Status",       width=8)
        for a in self._accounts:
            connected_at = (a.connected_at or "—")[:19].replace("T", " ")
            table.add_row(
                a.id[:14] + "…",
                a.provider,
                (a.display_name or "—")[:22],
                connected_at,
                a.status,
                key=a.id,
            )
        if self._accounts:
            table.focus()

    # ── Button clicks ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-kill":
            self._do_disconnect()
        elif event.button.id == "btn-view-id":
            self._do_view_id()

    # ── Key bindings ──────────────────────────────────────────────────────────

    def action_close(self) -> None:
        self.remove()

    def action_disconnect_selected(self) -> None:
        self._do_disconnect()

    def action_view_id(self) -> None:
        self._do_view_id()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _selected_account(self):
        table = self.query_one("#accounts-table", DataTable)
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._accounts):
            return None
        return self._accounts[row_idx]

    def _do_view_id(self) -> None:
        account = self._selected_account()
        if not account:
            return
        self.notify(
            f"[bold]{account.provider}[/bold] full ID:\n{account.id}",
            title="Account ID",
            severity="information",
            timeout=12,
        )

    def _do_disconnect(self) -> None:
        account = self._selected_account()
        if not account:
            return

        account_id = account.id
        row_idx = self.query_one("#accounts-table", DataTable).cursor_row

        try:
            from services.account_service import disconnect_account
            disconnect_account(self._session, account_id)
        except Exception as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        self._accounts.pop(row_idx)
        self.query_one("#accounts-table", DataTable).remove_row(account_id)

        self.notify(
            f"Disconnected {account.provider} — {account_id[:8]}…",
            severity="information",
            timeout=3,
        )
        self.post_message(self.Disconnected(account_id))

        if self._on_disconnect:
            self._on_disconnect(account_id)

        if not self._accounts:
            self.remove()
