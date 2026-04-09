"""
Orchestrator CLI entry point.
All subcommands are registered here.
"""
import typer
from typing import Annotated

from cli.commands import connect, accounts, model, route, trace, cache, agent

app = typer.Typer(
    name="orchestrator",
    help="Cost-aware LLM orchestration with semantic caching.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def app_callback(
    install_completion: Annotated[
        bool,
        typer.Option(
            "--install-completion",
            help="Install completion for the current shell.",
            is_eager=True,
        ),
    ] = False,
):
    """Root-level options for the CLI."""
    if install_completion:
        from typer.completion import install

        shell, path = install(prog_name="orchestrator")
        typer.secho(f"{shell} completion installed in {path}", fg="green")
        typer.echo("Completion will take effect once you restart the terminal")
        typer.secho("Installation completed.", fg="green")
        raise typer.Exit()


@app.command("init")
def cmd_init():
    """Initialise orchestrator home directory, database, and vector store."""
    from services.init_service import run_init
    run_init()


@app.command("list")
def cmd_list(
    resource: Annotated[
        str,
        typer.Argument(
            help="Resource to list: accounts | models | traces",
        ),
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

    print_error(
        "Unknown list resource. Use one of: accounts, models, traces."
    )
    raise typer.Exit(1)


app.command("connect", help="Connect a provider account.")(connect.cmd_connect)
app.command("route", help="Route a prompt to the cheapest model.")(route.cmd_route)
app.add_typer(accounts.app,  name="accounts", help="Manage connected accounts.", no_args_is_help=True)
app.add_typer(model.app,     name="model",    help="Browse the model registry.", no_args_is_help=True)
app.add_typer(trace.app,     name="trace",    help="Inspect routing traces.", no_args_is_help=True)
app.add_typer(cache.app,     name="cache",    help="Manage the semantic cache.", no_args_is_help=True)
app.add_typer(agent.app,     name="agent",    help="Tool-using agent (multi-provider).", no_args_is_help=True)


if __name__ == "__main__":
    app()
