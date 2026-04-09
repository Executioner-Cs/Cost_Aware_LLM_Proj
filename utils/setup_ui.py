"""Visual UI helpers for orchestrator first-time setup."""

from __future__ import annotations

from pathlib import Path

from rich.align import Align
from rich.panel import Panel
from rich.text import Text

from utils.console import console


_BANNER_LINES = [
    "  ██████╗ ██████╗  ██████╗██╗  ██╗███████╗███████╗████████╗██████╗  █████╗ ████████╗ ██████╗ ██████╗ ",
    " ██╔═══██╗██╔══██╗██╔════╝██║  ██║██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗",
    " ██║   ██║██████╔╝██║     ███████║█████╗  ███████╗   ██║   ██████╔╝███████║   ██║   ██║   ██║██████╔╝",
    " ██║   ██║██╔══██╗██║     ██╔══██║██╔══╝  ╚════██║   ██║   ██╔══██╗██╔══██║   ██║   ██║   ██║██╔══██╗",
    " ╚██████╔╝██║  ██║╚██████╗██║  ██║███████╗███████║   ██║   ██║  ██║██║  ██║   ██║   ╚██████╔╝██║  ██║",
    "  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝",
]

_ASCII_BANNER_LINES = [
    "  ____   ____   ____  _   _ ______  _____ _______ _____            _______ ____  _____ ",
    " / __ \\ |  _ \\ / ___|| | | |  ____|/ ____|__   __|  __ \\     /\\   |__   __/ __ \\|  __ \\",
    "| |  | || |_) | |    | |_| | |__  | (___    | |  | |__) |   /  \\     | | | |  | | |__) |",
    "| |  | ||  _ <| |    |  _  |  __|  \\___ \\   | |  |  _  /   / /\\ \\    | | | |  | |  _  /",
    "| |__| || |_) | |___ | | | | |____ ____) |  | |  | | \\ \\  / ____ \\   | | | |__| | | \\ \\",
    " \\____/ |____/ \\____||_| |_|______|_____/   |_|  |_|  \\_\\/_/    \\_\\  |_|  \\____/|_|  \\_\\",
]

_ASCII_COMPACT_BANNER_LINES = [
    "   ___  ____   ___ _  _ ____ ____ ___ ____ ____ ___ ____ ____ ",
    "  |  | |__/    |  |__| |___ [__   |  |__/ |__|  |  |  | |__/ ",
    "  |__| |  \\    |  |  | |___ ___]  |  |  \\ |  |  |  |__| |  \\ ",
]

_GRADIENT_STYLES = (
    "bright_cyan",
    "cyan",
    "bright_blue",
    "blue",
    "magenta",
    "bright_magenta",
)


def _supports_unicode_art() -> bool:
    encoding = (console.encoding or "").lower()
    # Legacy cp1252 and unknown encodings often fail on block glyphs.
    if not encoding:
        return False
    return "utf" in encoding


def render_init_banner() -> None:
    """Render a colorful, high-impact setup banner."""
    if _supports_unicode_art():
        lines = _BANNER_LINES
    elif console.width >= 110:
        lines = _ASCII_BANNER_LINES
    else:
        lines = _ASCII_COMPACT_BANNER_LINES
    banner = Text()
    for i, line in enumerate(lines):
        style = _GRADIENT_STYLES[i % len(_GRADIENT_STYLES)]
        banner.append(line + "\n", style=style + " bold")

    subtitle = Text(
        "Cost-aware multi-provider orchestration with semantic caching + agent tools",
        style="bright_white",
    )
    tips = Text(
        "Setup is preparing config, database, vector cache, and embeddings.\n"
        "This runs locally on your machine. First run may download model assets.",
        style="white",
    )
    body = Text()
    body.append_text(banner)
    body.append("\n")
    body.append_text(subtitle)
    body.append("\n\n")
    body.append_text(tips)

    panel = Panel(
        Align.left(body),
        title="[bold bright_green]ORCHESTRATOR INIT[/bold bright_green]",
        subtitle="[bold bright_black]visual setup mode[/bold bright_black]",
        border_style="bright_magenta",
        padding=(1, 2),
    )
    console.print(panel)


def render_init_success_panel(home: Path) -> None:
    """Render success summary + clear next steps."""
    ok = "✓" if _supports_unicode_art() else "+"
    lines = Text()
    lines.append(f"{ok} Setup complete.\n", style="bold green")
    lines.append(f"Config   : {home / 'config.toml'}\n", style="bright_white")
    lines.append(f"Database : {home / 'orchestrator.db'}\n", style="bright_white")
    lines.append(f"Vectors  : {home / 'qdrant'}\n", style="bright_white")
    lines.append("\nNext: interactive provider handoff starts now.\n", style="bold bright_cyan")
    lines.append("If interactive mode is unavailable or cancelled, use:\n", style="bright_white")
    lines.append("- orchestrator connect openai\n", style="cyan")
    lines.append("- orchestrator connect anthropic\n", style="cyan")
    lines.append("- orchestrator connect gemini\n", style="cyan")
    lines.append("- orchestrator connect groq\n", style="cyan")
    lines.append("- orchestrator model list\n", style="cyan")
    lines.append("- orchestrator route \"Summarize this text\"\n", style="cyan")
    lines.append("- orchestrator agent run \"Implement feature X\"\n", style="cyan")

    panel = Panel(
        Align.left(lines),
        title="[bold green]READY[/bold green]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)


def render_init_handoff_panel() -> None:
    """Render a compact Claude-like interactive handoff prompt."""
    lines = Text()
    lines.append("Interactive setup handoff\n", style="bold bright_cyan")
    lines.append("Select provider now (arrow keys + Enter).\n", style="bright_white")
    lines.append("Choose 'Skip for now' to continue manually.\n", style="bright_black")
    panel = Panel(
        Align.left(lines),
        title="[bold cyan]NEXT ACTION[/bold cyan]",
        border_style="cyan",
        padding=(0, 2),
    )
    console.print(panel)

