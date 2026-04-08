"""orchestrator route <prompt> [flags]"""
import typer
from typing import Annotated, Optional

app = typer.Typer()


@app.callback(invoke_without_command=True)
def route_prompt(
    prompt: Annotated[str, typer.Argument(help="Prompt to route")],
    task: Annotated[Optional[str], typer.Option("--task", "-t", help="Override task type")] = None,
    quality: Annotated[str, typer.Option("--quality", "-q", help="cheap | balanced | best")] = "balanced",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show routing plan without calling provider")] = False,
):
    """Route a prompt to the optimal LLM based on task and cost."""
    from db.session import get_session
    from core.router import route
    from schemas.routing import RouteRequest
    from utils.console import console, print_error

    request = RouteRequest(
        prompt=prompt,
        task_type=task,
        quality=quality,
        dry_run=dry_run,
    )

    try:
        session = get_session()
        result = route(request, session)
        session.close()
    except RuntimeError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    except Exception as exc:
        print_error(f"Unexpected error: {exc}")
        raise typer.Exit(1)

    # Display result
    from rich.panel import Panel
    from rich.table import Table

    meta = Table.grid(padding=(0, 2))
    meta.add_column(style="bold cyan", no_wrap=True)
    meta.add_column()

    meta.add_row("Task", result.task_type)
    meta.add_row("Route", result.route_reason)
    if result.provider:
        meta.add_row("Provider", result.provider)
    if result.model_id:
        meta.add_row("Model", result.model_id)

    cache_str = f"HIT  (similarity: {result.cache_similarity:.3f})" if result.cache_hit else "miss"
    meta.add_row("Cache", cache_str)

    if result.input_tokens is not None:
        tokens_str = f"{result.input_tokens} in"
        if result.output_tokens is not None:
            tokens_str += f" / {result.output_tokens} out"
        meta.add_row("Tokens", tokens_str)

    meta.add_row("Cost", f"${result.estimated_cost_usd:.6f}")

    if result.latency_ms is not None:
        meta.add_row("Latency", f"{result.latency_ms / 1000:.1f}s")

    console.print(meta)

    if result.response_text:
        console.print(Panel(result.response_text, title="Answer", border_style="green"))
    elif dry_run:
        console.print("[dim]Dry run — no provider call made.[/dim]")
