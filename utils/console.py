"""Rich console singleton + shared helpers."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _supports_unicode() -> bool:
    enc = (console.encoding or "").lower()
    return bool(enc) and "utf" in enc


def print_panel(title: str, body: str, style: str = "cyan") -> None:
    console.print(Panel(body, title=title, border_style=style))


def print_error(msg: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {msg}")


def print_success(msg: str) -> None:
    mark = "✓" if _supports_unicode() else "+"
    console.print(f"[bold green]{mark}[/bold green] {msg}")


def print_warning(msg: str) -> None:
    mark = "⚠" if _supports_unicode() else "!"
    console.print(f"[bold yellow]{mark}[/bold yellow] {msg}")
