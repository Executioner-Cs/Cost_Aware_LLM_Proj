"""
TUI Command Dispatcher.

Parses internal orchestrator> commands and calls service layer directly.
Returns Rich renderables that the TUI app writes to the RichLog.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.columns import Columns

from sqlalchemy.orm import Session


# ── Session state shared across TUI lifetime ────────────────────────────────

@dataclass
class SessionState:
    """Holds live handles kept open for the session."""
    session: Session
    home: Path
    config: dict
    quality: str = "balanced"

    # Derived stats (refreshed after each mutating command)
    provider_count: int = 0
    model_count: int = 0
    cache_enabled: bool = True
    monthly_budget: float = 0.0
    cost_this_session: float = 0.0

    def refresh_stats(self) -> None:
        from db.repositories.accounts import list_all
        from db.repositories.models import list_enabled
        accounts = list_all(self.session)
        self.provider_count = len([a for a in accounts if a.status == "active"])
        self.model_count = len(list_enabled(self.session))
        self.cache_enabled = self.config.get("cache", {}).get("enabled", True)
        self.monthly_budget = self.config.get("cost", {}).get("monthly_budget_usd", 0.0)


# ── Dispatcher ───────────────────────────────────────────────────────────────

HELP_TEXT = """\
[bold cyan]Orchestrator workbench[/bold cyan]  benchmark models on your own tasks, then route to the one that earned it.

[bold]Sources[/bold]
  [bold]connect[/bold]                       Open the Connect Center (pick a source).
  [bold]connect[/bold] [cyan]<provider>[/cyan] [--base-url URL]
      Cloud: anthropic | openai | groq | gemini  (key via env var or secure prompt)
      Local: connect ollama (keyless) | connect openai-compatible --base-url URL
  [bold]accounts[/bold] list | sync [cyan]<id>[/cyan] | disconnect [cyan]<id>[/cyan]
      Manage connected sources.
  [bold]model list[/bold]
      Show all discovered models.

[bold]Benchmarks[/bold]
  [bold]benchmark create[/bold] [cyan]<name>[/cyan] [--description D]
  [bold]benchmark add-task[/bold] [cyan]<set> <prompt>[/cyan] --expected E [--grader exact|contains|json_valid] [--task T]
  [bold]benchmark run[/bold] [cyan]<set>[/cyan] [--models m1,m2]
  [bold]benchmark scorecards[/bold] [--task-set S]
      Build task sets, run them across your models, and view local scorecards.

[bold]Routing[/bold]
  [bold]route[/bold] [cyan]<prompt>[/cyan] [--task T] [--quality Q] [--policy P] [--task-set S] [--dry-run]
      --task    : simple | json_extract | reasoning | vision | tools
      --quality : cheap | balanced (default) | best
      --policy  : auto | fast | best | cheap | local | private | deep | benchmarked
                  (no --policy = cheapest-capable default; auto adds a per-task quality
                   floor, which --quality best raises to the top tier)
      --task-set: scope the benchmarked policy to one task set's scorecards
  [bold]quality[/bold] [cyan]<cheap|balanced|best>[/cyan]
      Set the default quality tier for this session.

[bold]Inspect[/bold]
  [bold]trace[/bold] list [--limit N] | show [cyan]<id>[/cyan]
      Browse routing history.
  [bold]cache[/bold] stats | inspect [cyan]<id>[/cyan] | clear [--task-type T]
      Manage the exact-match response cache.

[bold]Session[/bold]
  [bold]init[/bold]                 Re-initialise the home directory (safe to re-run).
  [bold]clear[/bold]                Clear the output panel.
  [bold]help[/bold] | [bold]?[/bold]             Show this help.
  [bold]quit[/bold] | [bold]exit[/bold] | [bold]q[/bold]     Exit Orchestrator.
"""


class Dispatcher:
    def __init__(self, state: SessionState) -> None:
        self.state = state

    # ── Public entry point ───────────────────────────────────────────────────

    def dispatch(self, raw: str) -> list[Any]:
        """
        Parse *raw* command string and return a list of Rich renderables.
        Returns sentinel string "__clear__" to signal panel clear.
        Returns sentinel string "__quit__" to signal app exit.
        """
        raw = raw.strip()
        if not raw:
            return []

        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            return [Text(f"Parse error: {exc}", style="bold red")]

        cmd, *args = parts

        match cmd.lower():
            case "help" | "?":
                return [Panel(HELP_TEXT, title="Orchestrator Help", border_style="cyan")]

            case "quit" | "exit" | "q":
                return ["__quit__"]

            case "clear":
                return ["__clear__"]

            case "init":
                return self._cmd_init()

            case "route":
                return self._cmd_route(args)

            case "connect":
                return self._cmd_connect(args)

            case "accounts":
                return self._cmd_accounts(args)

            case "model":
                return self._cmd_model(args)

            case "trace":
                return self._cmd_trace(args)

            case "cache":
                return self._cmd_cache(args)

            case "benchmark":
                return self._cmd_benchmark(args)

            case "quality":
                return self._cmd_quality(args)

            case _:
                return [Text(
                    f"  Unknown command: '{cmd}'.  Type help for available commands.",
                    style="red"
                )]

    # ── Command handlers ─────────────────────────────────────────────────────

    def _cmd_init(self) -> list[Any]:
        from services.init_service import run_init
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        try:
            run_init(self.state.home)
            self.state.refresh_stats()
            return [Text("✓  Orchestrator initialised successfully.", style="bold green")]
        except Exception as exc:
            return [Text(f"Error during init: {exc}", style="bold red")]

    def _cmd_route(self, args: list[str]) -> list[Any]:
        import argparse
        from schemas.routing import RouteRequest
        from services.routing_service import route_prompt

        p = _silent_parser("route")
        p.add_argument("prompt", nargs="+")
        p.add_argument("--task", default=None)
        p.add_argument("--quality", default=self.state.quality)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--policy", default=None)
        p.add_argument("--task-set", dest="task_set", default=None)

        try:
            ns = p.parse_args(args)
        except SystemExit as exc:
            return [Text("Usage: route <prompt> [--task T] [--quality Q] [--policy P] [--task-set S] [--dry-run]", style="yellow")]

        prompt = " ".join(ns.prompt)
        request = RouteRequest(
            prompt=prompt,
            task_type=ns.task,
            quality=ns.quality,
            dry_run=ns.dry_run,
            policy=ns.policy,
            task_set=ns.task_set,
        )

        try:
            result = route_prompt(request, session=self.state.session)
        except Exception as exc:
            return [Text(f"Error: {exc}", style="bold red")]

        # Accumulate session cost
        self.state.cost_this_session += result.estimated_cost_usd

        # Build metadata grid
        meta = Table.grid(padding=(0, 2))
        meta.add_column(style="bold cyan", no_wrap=True)
        meta.add_column()

        meta.add_row("Task", result.task_type)
        meta.add_row("Route", result.route_reason)
        if result.provider:
            meta.add_row("Provider", result.provider)
        if result.model_id:
            meta.add_row("Model", result.model_id)

        if result.cache_hit:
            cache_str = f"[bold green]HIT[/bold green]  (similarity: {result.cache_similarity:.3f})"
        else:
            cache_str = "[dim]miss[/dim]"
        meta.add_row("Cache", cache_str)

        if result.input_tokens is not None:
            tokens_str = f"{result.input_tokens} in"
            if result.output_tokens:
                tokens_str += f" / {result.output_tokens} out"
            meta.add_row("Tokens", tokens_str)

        meta.add_row("Cost", f"${result.estimated_cost_usd:.6f}")
        if result.latency_ms is not None:
            # One decimal to match the `orchestrator route` CLI output exactly.
            meta.add_row("Latency", f"{result.latency_ms / 1000:.1f}s")

        renderables: list[Any] = [meta]

        if result.route_explanation:
            renderables.append(Text(result.route_explanation, style="dim"))

        if result.response_text:
            renderables.append(
                Panel(result.response_text, title="Answer", border_style="green")
            )
        elif ns.dry_run:
            renderables.append(Text("  [dry-run] No provider call made.", style="dim"))

        return renderables

    # The Connect Center: a product-grade source picker, shown for a bare
    # `connect`. Honest about how cloud keys are handled (no inline paste, no
    # fake browser sign-in) and which sources are keyless. The source names
    # listed here must stay in sync with _LOCAL_SOURCES below and the cloud
    # providers in connect_service._PROVIDER_CONNECTOR_MAP.
    _CONNECT_CENTER = (
        "[bold cyan]Connect a source[/bold cyan]\n\n"
        "[bold]Local[/bold] [dim](no cloud key)[/dim]\n"
        "  [bold]ollama[/bold]             Use your local Ollama models. No cloud key required.\n"
        "  [bold]openai-compatible[/bold]  Any local or custom OpenAI-style endpoint (--base-url URL).\n\n"
        "[bold]Cloud[/bold] [dim](secure terminal connection)[/dim]\n"
        "  [bold]openai[/bold], [bold]anthropic[/bold], [bold]gemini[/bold], [bold]groq[/bold]\n\n"
        "[dim]Cloud providers need an API key. Orchestrator reads it from your environment\n"
        "(e.g. OPENAI_API_KEY) or a secure hidden prompt, never from shell history, and\n"
        "stores it locally, encrypted. Browser/device sign-in is not offered.[/dim]\n\n"
        "[bold]Try[/bold]\n"
        "  [bold cyan]connect ollama[/bold cyan]\n"
        "  [bold cyan]connect openai[/bold cyan]"
    )

    _LOCAL_SOURCES = {"ollama", "openai-compatible", "openai_compatible"}

    def _cmd_connect(self, args: list[str]) -> list[Any]:
        # Bare `connect` opens the Connect Center rather than an argparse error.
        if not args:
            return [Panel(self._CONNECT_CENTER, title="Connect Center", border_style="cyan")]

        p = _silent_parser("connect")
        p.add_argument("provider")
        p.add_argument("--api-key", default=None)
        p.add_argument("--base-url", dest="base_url", default=None)
        try:
            ns = p.parse_args(args)
        except SystemExit:
            return [Text("Usage: connect <provider> [--base-url URL]   (type `connect` for options)", style="yellow")]

        provider = ns.provider.lower()

        # Local sources are keyless (Ollama) or keyed via the endpoint; connect directly.
        if provider in self._LOCAL_SOURCES:
            return self._do_connect(provider, ns.api_key or "", ns.base_url)

        # Cloud: an inline key still works but is gently discouraged (shell history).
        if ns.api_key:
            return self._do_connect(
                provider, ns.api_key, ns.base_url,
                tip=("Tip: an inline key is saved in your shell history. Next time set an "
                     f"env var or use the secure prompt: orchestrator connect {provider}."),
            )

        # Cloud: prefer an environment key so the connection stays in-shell and silent.
        from utils.env import load_dotenv_once, get_provider_api_key, get_provider_env_var
        load_dotenv_once()
        env_key = (get_provider_api_key(provider) or "").strip()
        if env_key:
            env_name = get_provider_env_var(provider) or "the environment"
            return self._do_connect(
                provider, env_key, ns.base_url,
                note=f"Using {env_name} from environment (not shown).",
            )

        # Cloud, no key available: guide the user to a secure setup. Never inline paste.
        return [self._secure_connect_guidance(provider)]

    def _secure_connect_guidance(self, provider: str) -> Panel:
        from utils.env import get_provider_env_var
        env_name = get_provider_env_var(provider) or f"{provider.upper()}_API_KEY"
        body = (
            f"{provider} needs an API key. Avoid passing it inline, which would save it "
            "in your shell history.\n\n"
            "[bold]Secure options[/bold]\n"
            f"  1. Set [bold]{env_name}[/bold] in your environment, then run  "
            f"[bold cyan]connect {provider}[/bold cyan]\n"
            f"  2. Run the secure hidden prompt in your terminal:  "
            f"[bold cyan]orchestrator connect {provider}[/bold cyan]\n"
            "     [dim]Your key is hidden as you type, never echoed, and stored locally encrypted.[/dim]\n\n"
            f"[dim]Browser or device sign-in is not available for {provider}; "
            "Orchestrator uses secure terminal setup instead.[/dim]"
        )
        return Panel(body, title=f"Connect {provider}", border_style="cyan")

    def _do_connect(
        self,
        provider: str,
        api_key: str,
        base_url: str | None,
        *,
        note: str | None = None,
        tip: str | None = None,
    ) -> list[Any]:
        # note/tip are only shown on success, so a failed connect never gets a
        # misleading "Using env var" prefix or a "shell history" footer.
        from services.connect_service import connect as svc_connect
        from db.repositories.models import list_for_account
        try:
            account = svc_connect(self.state.session, provider, api_key, base_url=base_url)
        except Exception as exc:
            return [Text(f"Could not connect {provider}: {exc}", style="bold red")]
        self.state.refresh_stats()
        count = len(list_for_account(self.state.session, account.id))
        where = f" at {account.base_url}" if account.base_url else ""
        stored = (
            "Credentials stored locally, encrypted."
            if account.encrypted_token else "Local source, no cloud key stored."
        )
        plural = "s" if count != 1 else ""
        out: list[Any] = []
        if note:
            out.append(Text(note, style="dim"))
        out.append(Text(
            f"✓  Connected {provider}{where}. {count} model{plural} discovered "
            f"(id: {account.id[:8]}…). {stored}",
            style="bold green",
        ))
        if tip:
            out.append(Text(tip, style="dim"))
        return out

    def _cmd_accounts(self, args: list[str]) -> list[Any]:
        if not args:
            return [Text("Usage: accounts list | sync <id> | disconnect <id>", style="yellow")]

        sub = args[0].lower()

        if sub == "list":
            from services.account_service import list_accounts
            from cli.tui.widgets import AccountsWidget
            accounts = list_accounts(self.state.session)
            if not accounts:
                return [Text("  No accounts connected. Type `connect` to choose a source.", style="yellow")]
            return [AccountsWidget(accounts, self.state.session)]

        elif sub == "sync":
            if len(args) < 2:
                return [Text("Usage: accounts sync <account-id>", style="yellow")]
            from services.account_service import sync_account
            try:
                sync_account(self.state.session, args[1])
                self.state.refresh_stats()
                return [Text(f"✓  Account {args[1][:8]}… synced.", style="green")]
            except Exception as exc:
                return [Text(f"Error: {exc}", style="bold red")]

        elif sub == "disconnect":
            if len(args) < 2:
                return [Text("Usage: accounts disconnect <account-id>", style="yellow")]
            from services.account_service import disconnect_account
            try:
                disconnect_account(self.state.session, args[1])
                self.state.refresh_stats()
                return [Text(f"✓  Account {args[1][:8]}… disconnected.", style="green")]
            except Exception as exc:
                return [Text(f"Error: {exc}", style="bold red")]

        return [Text(f"Unknown sub-command: accounts {sub}", style="red")]

    def _cmd_model(self, args: list[str]) -> list[Any]:
        if not args or args[0] != "list":
            return [Text("Usage: model list", style="yellow")]
        from services.model_service import list_models
        models = list_models(self.state.session)
        if not models:
            return [Text("  No models found. Run: connect <provider>", style="yellow")]
        table = Table(title="Model Registry", border_style="cyan")
        table.add_column("Provider")
        table.add_column("Model ID")
        table.add_column("Tier")
        table.add_column("Ctx")
        table.add_column("$/1M in", justify="right")
        table.add_column("$/1M out", justify="right")
        table.add_column("JSON")
        table.add_column("Tools")
        table.add_column("Vision")
        for m in models:
            ctx = f"{m.context_window // 1000}k" if m.context_window else "—"
            table.add_row(
                m.provider, m.external_model_id, m.tier, ctx,
                f"${m.cost_per_1m_input:.2f}" if m.cost_per_1m_input is not None else "—",
                f"${m.cost_per_1m_output:.2f}" if m.cost_per_1m_output is not None else "—",
                "✓" if m.supports_json else "✗",
                "✓" if m.supports_tools else "✗",
                "✓" if m.supports_vision else "✗",
            )
        return [table]

    def _cmd_trace(self, args: list[str]) -> list[Any]:
        if not args:
            return [Text("Usage: trace list [--limit N] | trace show <id>", style="yellow")]

        sub = args[0].lower()

        if sub == "list":
            limit = 15
            if "--limit" in args:
                try:
                    limit = int(args[args.index("--limit") + 1])
                except (ValueError, IndexError):
                    pass
            from services.trace_service import get_traces
            traces = get_traces(self.state.session, limit)
            if not traces:
                return [Text("  No traces yet.", style="dim")]
            table = Table(title=f"Recent Traces (last {limit})", border_style="cyan")
            table.add_column("ID", style="dim")
            table.add_column("Task")
            table.add_column("Provider")
            table.add_column("Cache")
            table.add_column("Cost", justify="right")
            table.add_column("Latency", justify="right")
            table.add_column("Status")
            for t in traces:
                cache_str = f"HIT {t.cache_similarity:.3f}" if t.cache_hit else "miss"
                cost_str = f"${t.estimated_cost_usd:.6f}" if t.estimated_cost_usd is not None else "—"
                lat_str = f"{t.latency_ms}ms" if t.latency_ms else "—"
                table.add_row(
                    (t.id or "")[:8] + "…",
                    t.task_type or "—",
                    t.provider or "—",
                    cache_str, cost_str, lat_str, t.status,
                )
            return [table]

        elif sub == "show":
            if len(args) < 2:
                return [Text("Usage: trace show <id>", style="yellow")]
            from services.trace_service import get_trace
            t = get_trace(self.state.session, args[1])
            if not t:
                return [Text(f"Trace '{args[1]}' not found.", style="red")]
            grid = Table.grid(padding=(0, 2))
            grid.add_column(style="bold cyan", no_wrap=True)
            grid.add_column()
            for k, v in [
                ("ID", t.id), ("Task", t.task_type or "—"),
                ("Route", t.route_reason or "—"), ("Provider", t.provider or "—"),
                ("Model", t.model_external_id or "—"),
                ("Cache Hit", "YES" if t.cache_hit else "NO"),
                ("Similarity", f"{t.cache_similarity:.4f}" if t.cache_similarity else "—"),
                ("Tokens", f"{t.input_tokens}/{t.output_tokens}" if t.input_tokens else "—"),
                ("Cost", f"${t.estimated_cost_usd:.6f}" if t.estimated_cost_usd is not None else "—"),
                ("Latency", f"{t.latency_ms}ms" if t.latency_ms else "—"),
                ("Status", t.status), ("Error", t.error_message or "—"),
                ("Created", t.created_at),
            ]:
                grid.add_row(k, v)
            renderables: list[Any] = [Panel(grid, title=f"Trace {(t.id or '')[:8]}…", border_style="cyan")]
            if t.prompt_preview:
                renderables.append(Panel(t.prompt_preview, title="Prompt", border_style="dim"))
            return renderables

        return [Text(f"Unknown: trace {sub}", style="red")]

    def _cmd_cache(self, args: list[str]) -> list[Any]:
        if not args:
            return [Text("Usage: cache stats | inspect <id> | clear", style="yellow")]

        sub = args[0].lower()
        from core.cache import get_cache, MissingFeatureError

        def _open_cache():
            return get_cache(self.state.config, self.state.session, self.state.home)

        if sub == "stats":
            try:
                c = _open_cache()
                stats = c.stats()
                c.close()
            except MissingFeatureError as exc:
                return [Text(str(exc), style="yellow")]
            except Exception as exc:
                return [Text(f"Cache unavailable: {exc}", style="red")]
            grid = Table.grid(padding=(0, 2))
            grid.add_column(style="bold cyan", no_wrap=True)
            grid.add_column()
            grid.add_row("Total entries", str(stats["total_entries"]))
            grid.add_row("Total hits", str(stats["total_hits"]))
            renderables: list[Any] = [Panel(grid, title="Cache Statistics", border_style="cyan")]
            if stats["top_entries"]:
                table = Table(title="Top Entries", border_style="dim")
                table.add_column("ID", style="dim")
                table.add_column("Preview")
                table.add_column("Hits", justify="right")
                for e in stats["top_entries"]:
                    table.add_row(e["id"][:8] + "…", e["response_preview"] + "…", str(e["hit_count"]))
                renderables.append(table)
            return renderables

        elif sub == "inspect":
            if len(args) < 2:
                return [Text("Usage: cache inspect <id>", style="yellow")]
            from db.repositories.cache import get_by_id
            entry = get_by_id(self.state.session, args[1])
            if not entry:
                return [Text(f"Cache entry '{args[1]}' not found.", style="red")]
            grid = Table.grid(padding=(0, 2))
            grid.add_column(style="bold cyan", no_wrap=True)
            grid.add_column()
            for k, v in [
                ("ID", entry.id), ("Task", entry.task_type), ("Quality", entry.quality),
                ("Provider", entry.provider or "—"), ("Model", entry.model_id or "—"),
                ("Hits", str(entry.hit_count or 0)), ("Created", entry.created_at),
                ("Last Hit", entry.last_hit_at or "—"),
            ]:
                grid.add_row(k, v)
            return [
                Panel(grid, title=f"Cache Entry {entry.id[:8]}…", border_style="cyan"),
                Panel(entry.response_text, title="Cached Response", border_style="green"),
            ]

        elif sub == "clear":
            task_type = None
            if "--task-type" in args:
                idx = args.index("--task-type")
                task_type = args[idx + 1] if idx + 1 < len(args) else None
            try:
                c = _open_cache()
                deleted = c.clear(task_type=task_type)
                c.close()
            except MissingFeatureError as exc:
                return [Text(str(exc), style="yellow")]
            except Exception as exc:
                return [Text(f"Error: {exc}", style="bold red")]
            return [Text(f"✓  Deleted {deleted} cache entries.", style="green")]

        return [Text(f"Unknown: cache {sub}", style="red")]

    # ── Benchmarks (workbench) ────────────────────────────────────────────────

    _BENCH_USAGE = (
        "Usage: benchmark create <name> [--description D] | "
        "add-task <set> <prompt> --expected E [--grader G] | "
        "run <set> [--models m1,m2] | scorecards [--task-set S]"
    )

    def _cmd_benchmark(self, args: list[str]) -> list[Any]:
        if not args:
            return [Text(self._BENCH_USAGE, style="yellow")]
        sub, rest = args[0].lower(), args[1:]
        if sub == "create":
            return self._bench_create(rest)
        if sub in ("add-task", "add_task"):
            return self._bench_add_task(rest)
        if sub == "run":
            return self._bench_run(rest)
        if sub == "scorecards":
            return self._bench_scorecards(rest)
        return [Text(f"Unknown: benchmark {sub}", style="red")]

    def _bench_create(self, args: list[str]) -> list[Any]:
        from services.benchmark_service import create_task_set

        p = _silent_parser("benchmark create")
        p.add_argument("name")
        p.add_argument("--description", "-d", default=None)
        try:
            ns = p.parse_args(args)
        except SystemExit:
            return [Text("Usage: benchmark create <name> [--description D]", style="yellow")]
        try:
            ts = create_task_set(self.state.session, ns.name, ns.description)
        except Exception as exc:
            return [Text(f"Error: {exc}", style="bold red")]
        return [Text(f"✓  Created task set '{ns.name}' (id: {ts.id[:8]}…)", style="green")]

    def _bench_add_task(self, args: list[str]) -> list[Any]:
        from core.benchmark import GRADERS
        from services.benchmark_service import get_task_set_by_name, add_task

        p = _silent_parser("benchmark add-task")
        p.add_argument("task_set")
        p.add_argument("prompt", nargs="+")
        p.add_argument("--expected", "-e", default=None)
        p.add_argument("--grader", "-g", default="contains")
        p.add_argument("--task", "-t", dest="task_type", default="simple")
        try:
            ns = p.parse_args(args)
        except SystemExit:
            return [Text("Usage: benchmark add-task <set> <prompt> --expected E [--grader exact|contains|json_valid]", style="yellow")]
        if ns.grader not in GRADERS:
            return [Text(f"grader must be one of: {' | '.join(GRADERS)}", style="yellow")]
        if ns.grader in ("exact", "contains") and not ns.expected:
            return [Text(f"grader '{ns.grader}' needs --expected; only json_valid runs without it.", style="yellow")]
        ts = get_task_set_by_name(self.state.session, ns.task_set)
        if not ts:
            return [Text(f"Task set '{ns.task_set}' not found. Create it with `benchmark create`.", style="red")]
        try:
            add_task(self.state.session, ts.id, " ".join(ns.prompt), ns.expected, ns.grader, ns.task_type)
        except Exception as exc:
            return [Text(f"Error: {exc}", style="bold red")]
        return [Text(f"✓  Added task to '{ns.task_set}'.", style="green")]

    def _bench_run(self, args: list[str]) -> list[Any]:
        import time
        from services.benchmark_service import get_task_set_by_name, run_benchmark, list_scorecards
        from db.repositories.models import list_enabled
        from db.repositories.accounts import get_by_id as get_account
        from providers.source import get_model_source
        from utils.crypto import decrypt

        p = _silent_parser("benchmark run")
        p.add_argument("task_set")
        p.add_argument("--models", "-m", default="")
        try:
            ns = p.parse_args(args)
        except SystemExit:
            return [Text("Usage: benchmark run <set> [--models m1,m2]", style="yellow")]

        session = self.state.session
        ts = get_task_set_by_name(session, ns.task_set)
        if not ts:
            return [Text(f"Task set '{ns.task_set}' not found.", style="red")]
        if not ts.tasks:
            # Running an empty set would write 0% scorecards for every model and
            # pollute future `benchmark scorecards` output. Refuse early.
            return [Text(
                f"Task set '{ns.task_set}' has no tasks. Add some with: benchmark add-task {ns.task_set} <prompt> --expected ...",
                style="yellow",
            )]
        wanted = {x.strip() for x in ns.models.split(",") if x.strip()}
        selected = [m for m in list_enabled(session) if (not wanted or m.external_model_id in wanted)]
        if not selected:
            return [Text("No matching enabled models. Connect a provider or source first.", style="yellow")]

        def generate_fn(model, prompt):
            account = get_account(session, model.account_id) if model.account_id else None
            api_key = decrypt(account.encrypted_token) if (account and account.encrypted_token) else ""
            source = get_model_source(
                model.provider,
                source_type=(account.source_type if account else None) or "cloud",
                base_url=(account.base_url if account else None),
            )
            t0 = time.monotonic()
            res = source.generate(prompt, model.external_model_id, api_key)
            latency = res.latency_ms if res.latency_ms is not None else int((time.monotonic() - t0) * 1000)
            cost = (
                (model.cost_per_1m_input or 0.0) * (res.input_tokens or 0)
                + (model.cost_per_1m_output or 0.0) * (res.output_tokens or 0)
            ) / 1_000_000
            return res.response_text, latency, cost

        try:
            run_benchmark(session, ts, selected, generate_fn)
            cards = list_scorecards(session, ts.id)
        except Exception as exc:
            return [Text(f"Benchmark run failed: {exc}", style="bold red")]
        return [self._scorecard_table(f"Scorecards: {ns.task_set}", cards)]

    def _bench_scorecards(self, args: list[str]) -> list[Any]:
        from services.benchmark_service import get_task_set_by_name, list_scorecards

        p = _silent_parser("benchmark scorecards")
        p.add_argument("--task-set", "-s", dest="task_set", default=None)
        try:
            ns = p.parse_args(args)
        except SystemExit:
            return [Text("Usage: benchmark scorecards [--task-set S]", style="yellow")]
        ts_id = None
        if ns.task_set:
            ts = get_task_set_by_name(self.state.session, ns.task_set)
            if not ts:
                return [Text(f"Task set '{ns.task_set}' not found.", style="red")]
            ts_id = ts.id
        cards = list_scorecards(self.state.session, ts_id)
        if not cards:
            return [Text("No scorecards yet. Run: benchmark run <task-set>", style="yellow")]
        return [self._scorecard_table("Scorecards", cards)]

    @staticmethod
    def _scorecard_table(title: str, cards) -> Table:
        table = Table(title=title, border_style="cyan")
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

    def _cmd_quality(self, args: list[str]) -> list[Any]:
        valid = {"cheap", "balanced", "best"}
        if not args or args[0] not in valid:
            return [Text(f"Usage: quality <cheap|balanced|best>  (current: {self.state.quality})", style="yellow")]
        self.state.quality = args[0]
        return [Text(f"✓  Default quality set to [bold]{args[0]}[/bold]", style="green")]


# ── Helper ───────────────────────────────────────────────────────────────────

def _silent_parser(prog: str):
    """argparse.ArgumentParser that raises SystemExit without printing."""
    import argparse

    class SilentParser(argparse.ArgumentParser):
        def error(self, message):
            raise SystemExit(message)
        def print_usage(self, file=None):
            pass
        def print_help(self, file=None):
            pass

    return SilentParser(prog=prog, add_help=False)
