"""orchestrator model list"""
import typer

app = typer.Typer()


@app.command("list")
def list_models():
    """List all models in the registry."""
    from db.session import get_session
    from services.model_service import list_models as svc_list
    from rich.table import Table
    from utils.console import console

    session = get_session()
    models = svc_list(session)
    session.close()

    if not models:
        console.print("[yellow]No models found. Run `orchestrator connect <provider>`[/yellow]")
        return

    table = Table(title="Model Registry")
    table.add_column("Provider")
    table.add_column("Model ID")
    table.add_column("Display Name")
    table.add_column("Tier")
    table.add_column("Ctx (k)")
    table.add_column("$/1M in", justify="right")
    table.add_column("$/1M out", justify="right")
    table.add_column("JSON")
    table.add_column("Tools")
    table.add_column("Vision")

    for m in models:
        ctx_k = f"{m.context_window // 1000}k" if m.context_window else "—"
        table.add_row(
            m.provider,
            m.external_model_id,
            m.display_name or "—",
            m.tier,
            ctx_k,
            f"${m.cost_per_1m_input:.2f}" if m.cost_per_1m_input is not None else "—",
            f"${m.cost_per_1m_output:.2f}" if m.cost_per_1m_output is not None else "—",
            "✓" if m.supports_json else "✗",
            "✓" if m.supports_tools else "✗",
            "✓" if m.supports_vision else "✗",
        )
    console.print(table)
