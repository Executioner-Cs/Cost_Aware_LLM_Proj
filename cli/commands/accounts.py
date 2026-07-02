"""orchestrator accounts list|sync|disconnect"""
import typer

app = typer.Typer(no_args_is_help=True)


@app.callback(invoke_without_command=True)
def accounts_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command("list")
def list_accounts():
    """List all connected provider accounts."""
    from db.session import get_session
    from services.account_service import list_accounts as svc_list
    from rich.table import Table
    from utils.console import console

    session = get_session()
    accounts = svc_list(session)
    session.close()

    if not accounts:
        console.print("[yellow]No accounts connected. Run `orchestrator connect <provider>`[/yellow]")
        return

    table = Table(title="Connected Accounts")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Provider")
    table.add_column("Display Name")
    table.add_column("Email")
    table.add_column("Status")
    table.add_column("Connected At")

    for a in accounts:
        table.add_row(
            a.id[:8] + "…",
            a.provider,
            a.display_name or "—",
            a.email or "—",
            a.status,
            a.connected_at[:10],
        )
    console.print(table)


@app.command("sync")
def sync_account(account_id: str = typer.Argument(..., help="Account ID to sync")):
    """Re-validate key and refresh model list for an account."""
    from db.session import get_session
    from services.account_service import sync_account as svc_sync
    from utils.console import print_success, print_error

    try:
        session = get_session()
        svc_sync(session, account_id)
        session.close()
        print_success(f"Account {account_id[:8]}… synced successfully.")
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@app.command("disconnect")
def disconnect_account(account_id: str = typer.Argument(..., help="Account ID to remove")):
    """Remove a connected account and its models."""
    confirm = typer.confirm(f"Disconnect account {account_id[:8]}…?")
    if not confirm:
        raise typer.Abort()

    from db.session import get_session
    from services.account_service import disconnect_account as svc_disconnect
    from utils.console import print_success, print_error

    try:
        session = get_session()
        svc_disconnect(session, account_id)
        session.close()
        print_success(f"Account {account_id[:8]}… disconnected.")
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
