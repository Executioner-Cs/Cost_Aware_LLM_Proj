"""orchestrator cache stats|inspect|clear|threshold"""
import typer
from typing import Annotated, Optional

app = typer.Typer(no_args_is_help=True)


@app.callback(invoke_without_command=True)
def cache_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command("stats")
def cache_stats():
    """Show cache statistics for the active cache mode."""
    from db.session import get_session
    from core.cache import get_cache, MissingFeatureError
    from services.init_service import get_home, load_config
    from rich.table import Table
    from rich.panel import Panel
    from utils.console import console, print_error

    home = get_home()
    config = load_config(home)
    mode = config.get("cache", {}).get("mode", "exact")

    session = get_session()
    try:
        cache = get_cache(config, session, home)
    except MissingFeatureError as exc:
        session.close()
        print_error(str(exc))
        raise typer.Exit(1)
    stats = cache.stats()
    cache.close()
    session.close()

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", no_wrap=True)
    grid.add_column()
    grid.add_row("Mode", mode)
    grid.add_row("Total entries", str(stats["total_entries"]))
    grid.add_row("Total hits", str(stats["total_hits"]))
    if mode == "semantic":
        threshold = config.get("cache", {}).get("similarity_threshold", 0.92)
        grid.add_row("Similarity threshold", str(threshold))

    console.print(Panel(grid, title="Cache Statistics", border_style="cyan"))

    if stats["top_entries"]:
        table = Table(title="Top Reused Entries")
        table.add_column("ID", style="dim")
        table.add_column("Preview")
        table.add_column("Hits", justify="right")
        table.add_column("Last Hit")
        for e in stats["top_entries"]:
            table.add_row(
                e["id"][:8] + "…",
                e["response_preview"] + "…",
                str(e["hit_count"]),
                (e["last_hit_at"] or "—")[:19],
            )
        console.print(table)


@app.command("inspect")
def cache_inspect(entry_id: str = typer.Argument(..., help="Cache entry ID")):
    """Inspect a specific cache entry."""
    from db.session import get_session
    from db.repositories.cache import get_by_id
    from rich.panel import Panel
    from rich.table import Table
    from utils.console import console, print_error

    session = get_session()
    entry = get_by_id(session, entry_id)
    session.close()

    if not entry:
        print_error(f"Cache entry '{entry_id}' not found.")
        raise typer.Exit(1)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", no_wrap=True)
    grid.add_column()
    rows = [
        ("ID", entry.id),
        ("Task Type", entry.task_type),
        ("Quality", entry.quality),
        ("Provider", entry.provider or "—"),
        ("Model", entry.model_id or "—"),
        ("Input Tokens", str(entry.input_tokens) if entry.input_tokens else "—"),
        ("Output Tokens", str(entry.output_tokens) if entry.output_tokens else "—"),
        ("Hit Count", str(entry.hit_count or 0)),
        ("Created At", entry.created_at),
        ("Last Hit At", entry.last_hit_at or "—"),
    ]
    for k, v in rows:
        grid.add_row(k, v)
    console.print(Panel(grid, title=f"Cache Entry {entry.id[:8]}…", border_style="cyan"))
    console.print(Panel(entry.response_text, title="Cached Response", border_style="green"))


@app.command("clear")
def cache_clear(
    task_type: Annotated[Optional[str], typer.Option("--task-type")] = None,
    older_than: Annotated[Optional[int], typer.Option("--older-than", help="Days")] = None,
):
    """Clear cache entries. Optionally filter by task-type or age."""
    from db.session import get_session
    from core.cache import get_cache, MissingFeatureError
    from services.init_service import get_home, load_config
    from utils.console import print_success, print_error

    confirm = typer.confirm("This will delete cache entries permanently. Continue?")
    if not confirm:
        raise typer.Abort()

    home = get_home()
    config = load_config(home)

    session = get_session()
    try:
        cache = get_cache(config, session, home)
    except MissingFeatureError as exc:
        session.close()
        print_error(str(exc))
        raise typer.Exit(1)
    deleted = cache.clear(task_type=task_type, older_than_days=older_than)
    cache.close()
    session.close()

    print_success(f"Deleted {deleted} cache entries.")


@app.command("threshold")
def cache_threshold(
    value: float = typer.Argument(..., help="New similarity threshold (0.0–1.0)"),
):
    """Set the similarity threshold in config.toml."""
    from services.init_service import get_home
    from utils.console import print_success, print_error
    import re

    if not (0.0 < value < 1.0):
        print_error("Threshold must be between 0 and 1 (exclusive).")
        raise typer.Exit(1)

    home = get_home()
    config_path = home / "config.toml"
    if not config_path.exists():
        print_error("config.toml not found. Run `orchestrator init` first.")
        raise typer.Exit(1)

    text = config_path.read_text()
    updated = re.sub(
        r"(similarity_threshold\s*=\s*)[0-9.]+",
        rf"\g<1>{value}",
        text,
    )
    config_path.write_text(updated)
    print_success(f"Similarity threshold set to {value}")
