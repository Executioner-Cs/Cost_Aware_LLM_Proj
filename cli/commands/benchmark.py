"""orchestrator benchmark create|add-task|run|scorecards

Benchmark connected models/sources on your own task sets and produce local
scorecards. Deterministic scoring only.
"""
import typer
from typing import Annotated

app = typer.Typer(no_args_is_help=True)


@app.callback(invoke_without_command=True)
def benchmark_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command("create")
def create(
    name: Annotated[str, typer.Argument(help="Task set name")],
    description: Annotated[str, typer.Option("--description", "-d")] = "",
):
    """Create a task set."""
    from db.session import get_session
    from services.benchmark_service import create_task_set
    from utils.console import print_success

    session = get_session()
    try:
        ts = create_task_set(session, name, description or None)
    finally:
        session.close()
    print_success(f"Created task set '{name}' (id: {ts.id[:8]}...)")


@app.command("add-task")
def add_task_cmd(
    task_set: Annotated[str, typer.Argument(help="Task set name")],
    prompt: Annotated[str, typer.Argument(help="Task prompt")],
    expected: Annotated[str, typer.Option("--expected", "-e")] = "",
    grader: Annotated[str, typer.Option("--grader", "-g", help="exact | contains | json_valid")] = "contains",
    task_type: Annotated[str, typer.Option("--task", "-t")] = "simple",
):
    """Add a task (prompt + expected answer + grader) to a task set."""
    from db.session import get_session
    from services.benchmark_service import get_task_set_by_name, add_task
    from core.benchmark import GRADERS
    from utils.console import print_success, print_error

    if grader not in GRADERS:
        print_error(f"grader must be one of {GRADERS}")
        raise typer.Exit(1)
    session = get_session()
    try:
        ts = get_task_set_by_name(session, task_set)
        if not ts:
            print_error(f"Task set '{task_set}' not found. Create it with `orchestrator benchmark create`.")
            raise typer.Exit(1)
        add_task(session, ts.id, prompt, expected or None, grader, task_type)
    finally:
        session.close()
    print_success(f"Added task to '{task_set}'.")


def _scorecard_table(title, cards):
    from rich.table import Table

    table = Table(title=title)
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Score", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Avg latency", justify="right")
    table.add_column("Avg cost", justify="right")
    for c in cards:
        table.add_row(
            c.provider, c.model_id, f"{c.score:.0%}",
            f"{c.tasks_passed}/{c.tasks_total}",
            f"{(c.avg_latency_ms or 0):.0f}ms", f"${(c.avg_cost_usd or 0):.6f}",
        )
    return table


@app.command("run")
def run_cmd(
    task_set: Annotated[str, typer.Argument(help="Task set name")],
    models: Annotated[str, typer.Option("--models", "-m", help="Comma-separated model ids; default all enabled")] = "",
):
    """Run a task set across selected models and store scorecards."""
    import time
    from db.session import get_session
    from db.repositories.models import list_enabled
    from db.repositories.accounts import get_by_id as get_account
    from services.benchmark_service import get_task_set_by_name, run_benchmark, list_scorecards
    from providers.source import get_model_source
    from utils.crypto import decrypt
    from utils.console import console, print_error

    session = get_session()
    try:
        ts = get_task_set_by_name(session, task_set)
        if not ts:
            print_error(f"Task set '{task_set}' not found.")
            raise typer.Exit(1)
        wanted = {x.strip() for x in models.split(",") if x.strip()}
        selected = [m for m in list_enabled(session) if (not wanted or m.external_model_id in wanted)]
        if not selected:
            print_error("No matching enabled models. Connect a provider or source first.")
            raise typer.Exit(1)

        def generate_fn(model, prompt):
            account = get_account(session, model.account_id) if model.account_id else None
            api_key = decrypt(account.encrypted_token) if (account and account.encrypted_token) else ""
            source = get_model_source(
                model.provider,
                source_type=(account.source_type if account else None) or "cloud",
                base_url=(account.base_url if account else None),
            )
            t0 = time.monotonic()
            result = source.generate(prompt, model.external_model_id, api_key)
            latency = result.latency_ms if result.latency_ms is not None else int((time.monotonic() - t0) * 1000)
            cost = (
                (model.cost_per_1m_input or 0.0) * (result.input_tokens or 0)
                + (model.cost_per_1m_output or 0.0) * (result.output_tokens or 0)
            ) / 1_000_000
            return result.response_text, latency, cost

        run_benchmark(session, ts, selected, generate_fn)
        cards = list_scorecards(session, ts.id)
    finally:
        session.close()

    console.print(_scorecard_table(f"Scorecards: {task_set}", cards))


@app.command("scorecards")
def scorecards_cmd(
    task_set: Annotated[str, typer.Option("--task-set", "-s", help="Filter by task set name")] = "",
):
    """Show stored scorecards (best score first)."""
    from db.session import get_session
    from services.benchmark_service import get_task_set_by_name, list_scorecards
    from utils.console import console

    session = get_session()
    try:
        ts_id = None
        if task_set:
            ts = get_task_set_by_name(session, task_set)
            ts_id = ts.id if ts else "__none__"
        cards = list_scorecards(session, ts_id)
    finally:
        session.close()
    if not cards:
        console.print("[yellow]No scorecards yet. Run `orchestrator benchmark run <task-set>`.[/yellow]")
        return
    console.print(_scorecard_table("Scorecards", cards))
