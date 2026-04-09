"""orchestrator connect <provider>"""
import typer
from typing import Annotated

def cmd_connect(
    provider: Annotated[str, typer.Argument(help="Provider: anthropic | openai | groq | gemini")],
    api_key: Annotated[str, typer.Option(
        prompt=True, hide_input=True, help="API key (PAT)"
    )] = "",
):
    """Connect a provider account using an API key."""
    from db.session import get_session
    from services.connect_service import connect as svc_connect
    from utils.console import console, print_success, print_error

    session = None
    try:
        with console.status(f"[cyan]Connecting to {provider}…"):
            session = get_session()
            account = svc_connect(session, provider, api_key)

            # Avoid DetachedInstanceError after session close/commit expiry.
            account_id = account.id
            display_name = account.display_name
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    except Exception as exc:
        print_error(f"Unexpected error: {exc}")
        raise typer.Exit(1)
    finally:
        if session is not None:
            session.close()

    print_success(
        f"Connected [bold]{provider}[/bold] account "
        f"[dim]{display_name or ''}[/dim] (id: {account_id[:8]}…)"
    )
