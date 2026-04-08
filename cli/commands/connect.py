"""orchestrator connect <provider>"""
import typer
from typing import Annotated

app = typer.Typer()


@app.callback(invoke_without_command=True)
def connect(
    provider: Annotated[str, typer.Argument(help="Provider name: anthropic | openai")],
    api_key: Annotated[str, typer.Option(
        prompt=True, hide_input=True, help="API key (PAT)"
    )] = "",
):
    """Connect a provider account using an API key."""
    from db.session import get_session
    from services.connect_service import connect as svc_connect
    from utils.console import console, print_success, print_error

    with console.status(f"[cyan]Connecting to {provider}…"):
        try:
            session = get_session()
            account = svc_connect(session, provider, api_key)
            session.close()
        except ValueError as exc:
            print_error(str(exc))
            raise typer.Exit(1)
        except Exception as exc:
            print_error(f"Unexpected error: {exc}")
            raise typer.Exit(1)

    print_success(
        f"Connected [bold]{provider}[/bold] account "
        f"[dim]{account.display_name or ''}[/dim] (id: {account.id[:8]}…)"
    )
