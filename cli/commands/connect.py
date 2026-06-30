"""orchestrator connect <provider>"""
import typer
from typing import Annotated

from db.session import get_session
from services.connect_service import connect as svc_connect
from utils.console import console, print_error, print_success
from utils.env import get_provider_api_key, get_provider_env_var, load_dotenv_once


def cmd_connect(
    provider: Annotated[str, typer.Argument(help="Provider: anthropic | openai | groq | gemini | ollama | openai-compatible")],
    api_key: Annotated[
        str,
        typer.Option(
            "--api-key",
            help="API key (PAT). Prefer an env var or the secure prompt; an inline key is saved in your shell history. If omitted, uses .env/env var, otherwise prompts (cloud providers).",
            hide_input=True,
        ),
    ] = "",
    base_url: Annotated[
        str,
        typer.Option(
            "--base-url",
            help="Endpoint for source types (ollama, openai-compatible), e.g. http://localhost:11434.",
        ),
    ] = "",
):
    """Connect a cloud provider (API key) or a source (ollama / openai-compatible base URL)."""
    session = None
    try:
        key = (api_key or "").strip()
        bu = (base_url or "").strip() or None
        is_source = bu is not None or provider.lower() in {"ollama", "openai-compatible", "openai_compatible"}

        if not key:
            load_dotenv_once()
            key = (get_provider_api_key(provider) or "").strip()
            if key:
                # Report the source (name only, never the value) so the user knows
                # no prompt is coming and the key did not have to be pasted.
                env_name = get_provider_env_var(provider) or "the environment"
                typer.echo(f"Using {env_name} from environment (not shown).")
        if not key and not is_source:
            key = typer.prompt(f"{provider} API key", hide_input=True).strip()
        if not key and not is_source:
            raise ValueError(
                "API key is required. Pass --api-key, set it in .env, or enter it at the prompt."
            )

        with console.status(f"[cyan]Connecting to {provider}..."):
            session = get_session()
            account = svc_connect(session, provider, key, base_url=bu)

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
