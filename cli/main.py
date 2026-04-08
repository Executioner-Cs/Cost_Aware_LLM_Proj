"""
Orchestrator CLI entry point.
All subcommands are registered here.
"""
import typer

from cli.commands import connect, accounts, model, route, trace, cache

app = typer.Typer(
    name="orchestrator",
    help="Cost-aware LLM orchestration with semantic caching.",
    no_args_is_help=True,
)


@app.command("init")
def cmd_init():
    """Initialise orchestrator home directory, database, and vector store."""
    from services.init_service import run_init
    run_init()


app.add_typer(connect.app,   name="connect",  help="Connect a provider account.")
app.add_typer(accounts.app,  name="accounts", help="Manage connected accounts.")
app.add_typer(model.app,     name="model",    help="Browse the model registry.")
app.add_typer(route.app,     name="route",    help="Route a prompt to the cheapest model.")
app.add_typer(trace.app,     name="trace",    help="Inspect routing traces.")
app.add_typer(cache.app,     name="cache",    help="Manage the semantic cache.")


if __name__ == "__main__":
    app()
