"""orchestrator agent — tool-using loop (multi-provider routing)."""
from __future__ import annotations

import typer
from typing import Annotated, Optional

app = typer.Typer(no_args_is_help=True, help="Run sandboxed agent with LLM tool calling.")


@app.callback(invoke_without_command=True)
def agent_root(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


def _run_goal(
    goal: str,
    quality: str,
    max_iterations: Optional[int],
    plan: bool,
    plan_llm: bool,
) -> None:
    from db.session import get_session
    from agent.loop import run_agent_loop
    from utils.console import console, print_error

    session = None
    try:
        session = get_session()
        with console.status("[cyan]Agent running…"):
            final, _msgs = run_agent_loop(
                session,
                goal,
                quality=quality,
                max_iterations=max_iterations,
                use_plan=plan,
                plan_llm=plan_llm,
            )
        console.print(final)
    except RuntimeError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    except Exception as exc:
        print_error(f"Agent failed: {exc}")
        raise typer.Exit(1)
    finally:
        if session is not None:
            session.close()


@app.command("run")
def cmd_run(
    goal: Annotated[str, typer.Argument(help="High-level task for the agent")],
    quality: Annotated[str, typer.Option("--quality", "-q", help="cheap | balanced | best")] = "balanced",
    max_iterations: Annotated[
        Optional[int],
        typer.Option("--max-iterations", "-n", help="Override config max_iterations"),
    ] = None,
    plan: Annotated[bool, typer.Option("--plan", help="Append planning preamble to system prompt")] = False,
    plan_llm: Annotated[
        bool,
        typer.Option("--plan-llm", help="With --plan, ask router for an LLM-generated step list first"),
    ] = False,
):
    """Run the agent loop until the model finishes or hits max iterations."""
    _run_goal(goal, quality, max_iterations, plan, plan_llm)


@app.command("edit")
def cmd_edit(
    path: Annotated[str, typer.Argument(help="File path (under sandbox) to modify")],
    instruction: Annotated[str, typer.Argument(help="What to change")],
    quality: Annotated[str, typer.Option("--quality", "-q")] = "balanced",
):
    goal = f"Edit file {path!r}: {instruction}. Use read_file before write_file; keep changes minimal."
    _run_goal(goal, quality, None, plan=True, plan_llm=False)


@app.command("explain")
def cmd_explain(
    path: Annotated[str, typer.Argument(help="File path under sandbox")],
    quality: Annotated[str, typer.Option("--quality", "-q")] = "balanced",
):
    goal = f"Read {path!r} and explain its purpose and structure clearly."
    _run_goal(goal, quality, None, plan=False, plan_llm=False)


@app.command("fix-tests")
def cmd_fix_tests(
    quality: Annotated[str, typer.Option("--quality", "-q")] = "balanced",
):
    goal = (
        "Run run_tests. If failures occur, read relevant files, fix the code, "
        "and re-run run_tests until passing or you cannot proceed."
    )
    _run_goal(goal, quality, 12, plan=True, plan_llm=False)


@app.command("refactor")
def cmd_refactor(
    target: Annotated[str, typer.Argument(help="Path or module description")],
    instruction: Annotated[str, typer.Argument(help="Refactoring goal")],
    quality: Annotated[str, typer.Option("--quality", "-q")] = "balanced",
):
    goal = f"Refactor {target!r}: {instruction}. Preserve behaviour; run_tests when done."
    _run_goal(goal, quality, 12, plan=True, plan_llm=False)
