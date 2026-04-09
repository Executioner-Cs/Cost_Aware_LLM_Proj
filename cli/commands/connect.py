"""orchestrator connect <provider>"""
import typer
from typing import Annotated

from db.session import get_session
from services.connect_service import connect as svc_connect
from utils.console import console, print_error, print_success
from utils.env import get_provider_api_key, load_dotenv_once


def cmd_connect(
    provider: Annotated[str, typer.Argument(help="Provider: anthropic | openai | groq | gemini")],
    api_key: Annotated[
        str,
        typer.Option(
            "--api-key",
            help="API key (PAT). If omitted, uses .env/env var; otherwise prompts.",
            hide_input=True,
        ),
    ] = "",
):
    """Connect a provider account using an API key."""
    session = None
    try:
        key = (api_key or "").strip()
        if not key:
            load_dotenv_once()
            key = (get_provider_api_key(provider) or "").strip()
        if not key:
            key = typer.prompt(
                f"{provider} API key",
                hide_input=True,
            ).strip()
        if not key:
            raise ValueError(
                "API key is required. Pass --api-key, set it in .env, or enter it at the prompt."
            )

        with console.status(f"[cyan]Connecting to {provider}..."):
            session = get_session()
            account = svc_connect(session, provider, key)

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
        f"[dim]{display_name or ''}[/dim] (id: {account_id[:8]}...)"
    )
