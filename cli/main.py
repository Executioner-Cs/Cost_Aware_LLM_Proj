"""
Orchestrator CLI entry point.

Hybrid behaviour:
  - ``orchestrator``               (no args, interactive TTY) → launch immersive TUI.
  - ``orchestrator``               (no args, non-interactive) → print help and exit.
  - ``orchestrator shell``                                    → launch immersive TUI explicitly.
  - ``orchestrator <subcommand>``                             → run subcommand normally.
"""
import sys
import typer
from typing import Annotated

from cli.commands import connect, accounts, model, route, trace, cache, agent, benchmark

app = typer.Typer(
    name="orchestrator",
    help="Cost-aware LLM orchestration with semantic caching.",
    no_args_is_help=False,    # changed: False so we can intercept no-arg invocations
    add_completion=False,
)


# ── Hybrid entrypoint: no-arg on a TTY launches the immersive TUI ───────────

@app.callback(invoke_without_command=True)
def app_callback(
    ctx: typer.Context,
    install_completion: Annotated[
        bool,
        typer.Option(
            "--install-completion",
            help="Install completion for the current shell.",
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Root-level options. Running with no subcommand on a TTY launches the TUI."""
    if install_completion:
        from typer.completion import install
        shell, path = install(prog_name="orchestrator")
        typer.secho(f"{shell} completion installed in {path}", fg="green")
        typer.echo("Completion will take effect once you restart the terminal")
        typer.secho("Installation completed.", fg="green")
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return  # sub-command will handle everything

    if _is_interactive_tty():
        _launch_tui()
    else:
        typer.echo(ctx.get_help())
        raise typer.Exit()


def _is_interactive_tty() -> bool:
    return (
        hasattr(sys.stdin, "isatty") and sys.stdin.isatty() and
        hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    )


def _launch_tui() -> None:
    try:
        from cli.tui.app import create_app
    except ModuleNotFoundError as exc:
        if (exc.name or "").split(".")[0] in ("textual", "questionary"):
            typer.secho(
                'The TUI requires the tui extra. Install with: '
                'pip install "orchestrator-cli[tui]" or use CLI commands directly.',
                fg="yellow",
                err=True,
            )
            raise typer.Exit(1) from exc
        raise
    tui = create_app()
    tui.run()


# ── Named commands ───────────────────────────────────────────────────────────

@app.command("init")
def cmd_init():
    """Initialise orchestrator home directory, database, and vector store."""
    from services.init_service import run_init
    run_init()
    if _is_interactive_tty():
        _launch_tui()


@app.command("shell")
def cmd_shell():
    """Launch the immersive full-screen TUI (same as bare `orchestrator` on a TTY)."""
    _launch_tui()


@app.command("list")
def cmd_list(
    resource: Annotated[
        str,
        typer.Argument(help="Resource to list: accounts | models | traces"),
    ] = "accounts",
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Limit for traces list"),
    ] = 20,
):
    """Convenience listing command for common resources."""
    from utils.console import print_error

    key = resource.strip().lower()
    if key in {"account", "accounts"}:
        accounts.list_accounts()
        return
    if key in {"model", "models"}:
        model.list_models()
        return
    if key in {"trace", "traces"}:
        trace.list_traces(limit=limit)
        return

    print_error("Unknown list resource. Use one of: accounts, models, traces.")
    raise typer.Exit(1)


# ── Sub-command registration (unchanged from main) ───────────────────────────

app.command("connect", help="Connect a provider account.")(connect.cmd_connect)
app.command("route",   help="Route a prompt to the cheapest model.")(route.cmd_route)
app.add_typer(accounts.app, name="accounts", help="Manage connected accounts.",    no_args_is_help=True)
app.add_typer(model.app,    name="model",    help="Browse the model registry.",    no_args_is_help=True)
app.add_typer(trace.app,    name="trace",    help="Inspect routing traces.",        no_args_is_help=True)
app.add_typer(cache.app,    name="cache",    help="Manage the semantic cache.",     no_args_is_help=True)
app.add_typer(agent.app,    name="agent",    help="Tool-using agent (multi-provider).", no_args_is_help=True)
app.add_typer(benchmark.app, name="benchmark", help="Benchmark models on your own task sets.", no_args_is_help=True)


if __name__ == "__main__":
    app()
