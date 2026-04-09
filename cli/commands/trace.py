"""orchestrator trace list|show"""
import typer
from typing import Optional

app = typer.Typer(no_args_is_help=True)


@app.callback(invoke_without_command=True)
def trace_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command("list")
def list_traces(limit: int = typer.Option(20, "--limit", "-n", help="Number of traces to show")):
    """List recent routing traces."""
    from db.session import get_session
    from services.trace_service import get_traces
    from rich.table import Table
    from utils.console import console

    session = get_session()
    traces = get_traces(session, limit)
    session.close()

    if not traces:
        console.print("[yellow]No traces found.[/yellow]")
        return

    table = Table(title=f"Recent Traces (last {limit})")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Task")
    table.add_column("Provider")
    table.add_column("Model", no_wrap=True)
    table.add_column("Cache")
    table.add_column("Tokens")
    table.add_column("Cost", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Status")
    table.add_column("Created")

    for t in traces:
        cache_str = f"HIT {t.cache_similarity:.3f}" if t.cache_hit else "miss"
        tokens_str = (
            f"{t.input_tokens}/{t.output_tokens}"
            if t.input_tokens is not None else "—"
        )
        cost_str = f"${t.estimated_cost_usd:.6f}" if t.estimated_cost_usd is not None else "—"
        latency_str = f"{t.latency_ms}ms" if t.latency_ms is not None else "—"

        table.add_row(
            (t.id or "")[:8] + "…",
            t.task_type or "—",
            t.provider or "—",
            (t.model_external_id or "—")[:20],
            cache_str,
            tokens_str,
            cost_str,
            latency_str,
            t.status,
            (t.created_at or "")[:19],
        )
    console.print(table)


@app.command("show")
def show_trace(trace_id: str = typer.Argument(..., help="Trace ID")):
    """Show details for a single trace."""
    from db.session import get_session
    from services.trace_service import get_trace
    from rich.panel import Panel
    from rich.table import Table
    from utils.console import console, print_error

    session = get_session()
    trace = get_trace(session, trace_id)
    session.close()

    if not trace:
        print_error(f"Trace '{trace_id}' not found.")
        raise typer.Exit(1)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", no_wrap=True)
    grid.add_column()

    rows = [
        ("ID", trace.id),
        ("Task", trace.task_type or "—"),
        ("Route Reason", trace.route_reason or "—"),
        ("Provider", trace.provider or "—"),
        ("Model", trace.model_external_id or "—"),
        ("Cache Hit", "YES" if trace.cache_hit else "NO"),
        ("Cache Similarity", f"{trace.cache_similarity:.4f}" if trace.cache_similarity else "—"),
        ("Input Tokens", str(trace.input_tokens) if trace.input_tokens else "—"),
        ("Output Tokens", str(trace.output_tokens) if trace.output_tokens else "—"),
        ("Estimated Cost", f"${trace.estimated_cost_usd:.6f}" if trace.estimated_cost_usd is not None else "—"),
        ("Latency", f"{trace.latency_ms}ms" if trace.latency_ms else "—"),
        ("Status", trace.status),
        ("Error", trace.error_message or "—"),
        ("Created At", trace.created_at),
    ]
    for k, v in rows:
        grid.add_row(k, v)

    console.print(Panel(grid, title=f"Trace {trace.id[:8]}…", border_style="cyan"))
    if trace.prompt_preview:
        console.print(Panel(trace.prompt_preview, title="Prompt Preview", border_style="dim"))
