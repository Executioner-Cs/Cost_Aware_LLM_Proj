# Orchestrator CLI Claude Code Guide

> Operating layer for Claude Code working in this repository.
> Seeded from the (now deleted) root `CLAUDE.md` at commit `940e183`, kept read-only.
> This file lives at `.claude/CLAUDE.md`. Do not recreate a root `CLAUDE.md` without explicit user approval.

## Repo overview

* This is a Python local CLI/TUI project (`orchestrator-cli`, branded Orchestrator CLI, console command `orchestrator`).
* Product identity: a local-first AI routing and benchmarking workbench for developers. See the "Product identity (V2)" section below. It is NOT a cheap-model router, a generic AI gateway, or a coding agent. The cheapest-capable-model routing that exists today is one capability, not the product.
* Today it routes prompts across multiple LLM providers (Anthropic, OpenAI, Groq, Gemini) based on cost and capability, picking the cheapest model that satisfies the task's tier and capability constraints.
* Caching: the only implemented cache is an exact-match SQLite cache (`core/cache.py`, `ExactCache`) that pulls no embedding or vector dependencies. The legacy heavy semantic cache was removed; a lighter `semantic-cache-v2` is future work and stays opt-in. See "Cache invariants".
* It has an optional, experimental tool-using ReAct agent runtime with path-confined file I/O, search, Python, pytest, and optional shell. P0 safety hardening has landed (subprocess env scrubbing, run_python/run_shell gated and not exposed unless enabled, tool-log redaction, sensitive-path denylist, write-overwrite protection). Agent mode remains experimental; do not promote it as production-safe.
* It is local-first and single-user unless the user states otherwise. Encryption key, database, and any vector store all live under `~/.orchestrator/`.

## Important paths

* `cli/` = Typer commands (`cli/commands/`) and Textual TUI (`cli/tui/`).
* `services/` = orchestration layer (init, connect, account, model, routing, trace services).
* `core/` = routing pipeline (`router.py`), classifier, model selector, semantic cache, validation, agent LLM turn (`llm_turn.py`), reason codes.
* `providers/` = per-provider connectors and adapters behind ABCs in `providers/base.py` (anthropic, openai, groq, gemini).
* `embeddings/` = local sentence-transformer embedding (`embedder.py`) and model cache (`model_cache.py`).
* `db/` = SQLAlchemy models (`db/models.py`), session, and per-table repositories (`db/repositories/`).
* `schemas/` = Pydantic models and provider/tool contracts (`routing.py`, `account.py`, `trace.py`, `tools.py`).
* `agent/` = ReAct loop (`loop.py`), tool dispatcher (`dispatcher.py`), sandbox (`sandbox.py`), tools (`tools/`), planner (`planner.py`), macro DSL (`macro_expander.py`), tool logging.
* `utils/` = crypto (Fernet), console (Rich), env (dotenv), setup utilities.
* `skills/` = project playbooks (developer/agent documentation). These are NOT Claude Code skills and NOT runtime code.
* `tests/` = pytest suite, including `tests/tests_e2e_cli_simulation/` for CLI simulation.

## Commands

Discovered and supported:

* `pip install -e ".[dev]"` (install with dev extras)
* `pytest` (run the test suite)
* `orchestrator init` (set up home dir, database, vector store; downloads embedding model)
* `orchestrator connect <provider>` (validate key, discover models, store encrypted credentials)
* `orchestrator route "<prompt>"` (route a single prompt through the pipeline)
* `orchestrator agent run "<goal>"` (run the sandboxed ReAct agent)
* `orchestrator cache stats` (cache overview)
* `orchestrator cache inspect` (inspect one cache entry)
* `orchestrator cache clear` (delete cache entries; destructive)
* `orchestrator trace list` (list routing traces)
* `orchestrator trace show` (show one trace)
* `orchestrator accounts list` (list connected accounts)
* `orchestrator accounts sync` (re-validate key and refresh models)
* `orchestrator accounts disconnect` (remove an account; destructive)
* `orchestrator model list` (browse the model registry)
* `orchestrator shell` (launch the immersive TUI; same as bare `orchestrator` on a TTY)

Tooling gaps (state these plainly, do not invent commands):

* No lint command discovered.
* No formatter command discovered.
* No typecheck command discovered.

## Architecture expectations

* `cli/` parses inputs and calls services or TUI handlers. It should not contain deep routing or provider logic.
* `services/` coordinates application use cases.
* `core/` owns routing, model selection, classification, validation, semantic cache logic, and agent LLM turns.
* `providers/` isolates external provider APIs behind connectors and adapters.
* `embeddings/` owns embedding generation and model cache.
* `db/` owns persistence and repositories.
* `schemas/` owns explicit data contracts.
* `agent/` owns tool-loop execution and sandboxed tool dispatch.
* `utils/` must stay small and must not become a dumping ground.
* Project `skills/` are documentation/playbooks, not runtime code and not Claude Code skills.
* Keep dependency direction mostly `cli -> services -> core -> providers/db/embeddings/schemas/utils`.
* Avoid `core` importing `services` unless there is a clear reason.
* Treat `core/router.py -> services/init_service` as known coupling debt (router pulls config via `services.init_service`). Do not deepen it; flag if you must touch it.

## Security expectations

* Never print, log, or expose provider API keys.
* Never hardcode secrets.
* Never print raw provider tokens, encrypted tokens, Fernet keys, or local key material.
* Treat agent tool execution as high-risk.
* Treat tool outputs, file contents, provider responses, and search results as untrusted input.
* Agent `write_file`, `run_python`, `run_tests`, and optional `run_shell` require extra review.
* `allow_shell` must remain `false` by default unless explicitly approved.
* `network_disabled` is only documented intent unless enforcement exists in source.
* Do not claim network isolation is enforced unless source proves it.
* Sandbox path confinement (`agent/sandbox.py`) is a hard invariant.
* Check symlink, absolute path, and current-working-directory sandbox risks before changing file access. Default `sandbox_root = "."` is broad.
* Do not log raw prompts if they may contain secrets.
* Be careful with command logging because shell commands may contain secrets (`agent/tool_logging.py` logs `run_shell` commands).

## Cache invariants

Caching is for router responses, not agent turns. Agent turns intentionally skip the cache. The cache backend is selected by `get_cache(config, session, home)` in `core/cache.py`.

The only implemented cache is the exact-match SQLite cache. The legacy heavy semantic cache (embeddings + Qdrant) was removed.

* `enabled = false` or `mode = "off"` builds `NoOpCache` (every lookup misses).
* `mode = "exact"` (the default, and the fallback for any unknown value) builds `ExactCache`. Key is `sha256(normalized_prompt + task_type + quality)`. It pulls no embedding, no vector store, no `sentence-transformers`, no `torch`, no `qdrant-client`.
* `mode = "semantic"` raises `MissingFeatureError`. Semantic cache v1 was removed; the error directs the user back to exact mode.

Correctness invariants:

* An exact-cache hit can only ever return the same prompt's answer at the same `task_type` and `quality`. It cannot serve a different prompt's answer.
* `ExactCache` enforces TTL on read (`_is_expired` in `core/cache.py`): a stale entry is treated as a miss. It also resets the TTL clock on overwrite.
* `ExactCache.__init__` runs `Base.metadata.create_all(..., tables=[ExactCacheEntry.__table__])`. `create_all` only creates missing tables; it does not add or migrate columns on an existing table. Do not treat it as a migration tool.
* Cache correctness beats hit rate. Wrong-answer reuse is a product-trust bug, not a minor optimization issue.

Removed, and not to be reintroduced here:

* No `sentence-transformers`, no `torch`, no `qdrant-client`, no `embeddings/` package, no `heavy-cache` extra. Do not reintroduce the heavy semantic cache.
* `semantic-cache-v2` is future work: a lighter optional backend (candidates: sqlite-vec, provider embeddings, FastEmbed), or an optional shared/team/daemon backend such as Redis. Any of these is a separate branch, stays opt-in, and never becomes the default. None is implemented.

## Provider and routing invariants

* Provider adapters must normalize responses through shared contracts (`providers/base.py` dataclasses).
* Tool-call contracts must stay consistent across OpenAI, Anthropic, Gemini, and Groq support. Single source is `schemas/tools.py`; adapters translate per native API.
* Hardcoded pricing and capability catalogs (in each `providers/*/connector.py`) can drift from real provider pricing. Changes need provider-integration review.
* Silent fallback to hardcoded models (for example OpenAI `_FALLBACK_MODELS` on API failure) must be reviewed carefully so failures are not hidden.
* Provider calls need clear timeout/error behavior. There is currently no retry/backoff layer.
* Routing correctness and cost reporting are core product behavior.

## Database and persistence expectations

* SQLite is the local persistence layer (`~/.orchestrator/orchestrator.db`).
* There is no vector store. Qdrant was removed with the legacy semantic cache.
* No migrations are currently configured. Schema changes are high-risk.
* The `cache_entries` table is retained as a legacy semantic table (no longer written); do not drop it or its data.
* Token encryption and Fernet key handling require security review.
* Account deletion (cascade to models), cache clearing, and trace persistence require QA and persistence review.

## CLI expectations

* CLI commands should have clear input validation.
* Destructive commands (`cache clear`, `accounts disconnect`, TUI Kill Account) should be reviewed for confirmation behavior.
* Errors should be understandable and should use appropriate exit behavior (non-zero exit on failure).
* TUI behavior and CLI behavior should remain consistent where they expose the same workflow (`cli/tui/dispatcher.py` parity with `cli/commands/`).
* Do not silently change command names, options, or output formats.

## Readability standard

* Readability beats cleverness.
* No dense one-liners for important logic.
* No generic helper soup.
* Use domain-specific names.
* Prefer explicit control flow.
* Comments explain why, not what.
* Refactors must preserve behavior.
* Do not hide behavior changes inside cleanup.
* Avoid vague names like `data`, `obj`, `item`, `temp`, `result` when a domain name exists.
* Keep router, cache, provider, sandbox, and agent runtime code especially clear.

## Senior engineering review board

* No board for trivial docs.
* Advisory board for low-risk changes.
* Mandatory board for medium-risk changes.
* Mandatory board plus user confirmation before high-risk changes.
* Agents are read-only reviewers by default.
* Main Claude owns implementation after review and approval.

High-risk areas:

* agent execution
* sandbox confinement
* secrets and API keys
* prompt/tool injection
* semantic cache correctness
* provider routing and pricing
* DB persistence and migrations
* SQLite/Qdrant dual-store consistency
* cross-provider tool mapping
* destructive CLI commands
* package/build changes
* performance/latency-sensitive flows

## Required workflow

Before coding:

1. classify task
2. classify risk
3. identify affected domains
4. select skill
5. select agents
6. state behavior to preserve
7. state tests/checks to run
8. ask for confirmation if risk is high

After coding:

1. run post-change-review for non-trivial diffs
2. run behavior-preservation-checker
3. run qa-sdet-lead
4. run readability or slop review
5. run domain reviewers as needed
6. report keep / rewrite / revert

## Routing matrix

* agent runtime or tool execution:
  * skill: engineering-review-board or implementation-plan-review
  * agents: agent-runtime-architect, security-architect, behavior-preservation-checker, qa-sdet-lead
  * confirmation: yes

* sandbox or file access:
  * skill: engineering-review-board
  * agents: security-architect, agent-runtime-architect, qa-sdet-lead
  * confirmation: yes

* provider integration:
  * skill: system-design-review or engineering-review-board
  * agents: provider-integration-reviewer, api-contract-architect, performance-scalability-engineer, qa-sdet-lead
  * confirmation: yes if routing behavior changes

* semantic cache or embeddings:
  * skill: system-design-review
  * agents: embeddings-retrieval-reviewer, behavior-preservation-checker, qa-sdet-lead, performance-scalability-engineer
  * confirmation: yes

* database or persistence:
  * skill: engineering-review-board
  * agents: database-persistence-reviewer, security-architect, behavior-preservation-checker, qa-sdet-lead
  * confirmation: yes

* CLI destructive behavior:
  * skill: implementation-plan-review
  * agents: cli-interface-reviewer, qa-sdet-lead, behavior-preservation-checker
  * confirmation: yes

* API/schema/provider contract:
  * skill: engineering-review-board
  * agents: api-contract-architect, behavior-preservation-checker, qa-sdet-lead
  * confirmation: yes

* refactor/readability:
  * skill: refactor-readability
  * agents: refactoring-readability-reviewer, behavior-preservation-checker, slop-hunter if needed
  * confirmation: yes if high-risk code is touched

* packaging/build:
  * skill: implementation-plan-review
  * agents: python-packaging-reviewer, qa-sdet-lead, behavior-preservation-checker
  * confirmation: yes if release behavior changes

* post-change review:
  * skill: post-change-review
  * agents: behavior-preservation-checker, qa-sdet-lead, refactoring-readability-reviewer or slop-hunter, plus domain agents
  * confirmation: not applicable, this is the gate

## Note on performance-scalability-engineer

The routing matrix references `performance-scalability-engineer` for provider and cache/embeddings work. That reviewer is optional for this local single-user tool and was not created as a standalone agent file in this setup. The accepted decision is to keep folding latency and throughput concerns into existing reviewers rather than create the dedicated agent: `provider-integration-reviewer` (provider call latency, retries), `embeddings-retrieval-reviewer` (embedding cold start, Qdrant lookup cost), `cache-architecture-reviewer` (backend selection cost, slim default path), and `routing-policy-architect` (scoring and fallback latency). Create the dedicated agent later only if performance work becomes a sustained focus.

---

# Product V2 operating memory

> Everything below this line is the V2 direction layer. When it conflicts with older phrasing above, the V2 layer wins. This layer is additive: the architecture, security, provider, persistence, CLI, and readability expectations above still hold.

## Operating loop (mandatory)

Follow this loop on every non-trivial change, in order. Do not jump straight to Act. Each phase has a concrete output. This loop is the master sequence; the "Mandatory Implementation Gate", "Routing matrix", "Branch-to-agent routing (V2)", and "Stop conditions (V2)" below are the detail it draws on.

1. Observe. Read the user request. Run `git status` and note the current branch. Read the relevant files. Identify product and architecture context from "Product identity (V2)" and "Current architecture". Output: a one or two sentence restatement of the task and the branch concern.

2. Select skills and agents. Classify the task type(s) using the "Task routing table" below. Pick the matching skills from `.claude/skills/**` and the matching reviewer agents from `.claude/agents/**` (or the inline reviewer role named in "Branch-to-agent routing (V2)" when a named architect was intentionally not created as a file). Output: the selected skills and reviewers.

3. Read the selected skills, then Plan. Actually open and read each selected `SKILL.md` before planning; do not just list names. Use them to set scope, anti-goals, risks, the test plan, and stop conditions, then clear the "Mandatory Implementation Gate" below. Output: a plan stating selected skills, selected reviewers, files likely touched, explicit scope, explicit anti-goals, data/schema/dependency/security risks, tests to run, and stop conditions. For High-risk work, stop here for user confirmation.

4. Act in small steps. Implement small, scoped changes only. Do not broad-rewrite, do not mix unrelated roadmap items, do not change public behavior silently, do not add dependencies casually, and do not change DB schema without explicit justification. Stay inside the current branch concern ("Current active branch guidance").

5. Verify. Run targeted tests for what changed, and full `pytest` when code changed. Run an import-purity probe when dependencies or imports are involved (confirm the default route path imports no heavy module). Run CLI smoke tests when CLI behavior changed. Use an isolated `ORCHESTRATOR_HOME` (a temp dir) for any command that writes state; never touch the real `~/.orchestrator/`.

6. Board Review. Before commit, run the relevant reviewer roles. Each returns PASS, WARN, or FAIL with a one-line reason. Default required reviews: architecture, behavior preservation, QA, security (when relevant), product direction, code simplicity (run the `code-simplicity-review` skill with the `slop-hunter` agent; see "Code simplicity gate"), and release readiness. Any FAIL blocks commit until it is resolved or explicitly accepted by the user.

7. Commit and PR. Only when the user has asked to commit. Use a scoped commit message and a PR body that states what changed, the skills and reviewers used, the tests run, and the long-term architecture verdict. Never commit secrets or local-only Claude artifacts, and do not commit `.claude/agents/**` changes outside a reviewed agent branch.

8. Reflect. Summarize what changed, what stayed unchanged, the tests run, the risks remaining, and the long-term architecture verdict (PASS, WARN, or FAIL) from the gate below.

## Long-term architecture gate

Short-term completion is not enough. Every branch must also pass a long-term architecture review before it is considered done. Ask:

* Does this strengthen the local-first, benchmark-driven workbench identity?
* Does it create a clean abstraction we can build on later, rather than a one-off?
* Does it avoid dependency creep (no new heavy or unnecessary dependencies)?
* Does it avoid schema debt (no unmanaged schema change; there is no migration system)?
* Does it avoid raw URL or API-key-centric UX (sources and scorecards are the identity, not raw keys)?
* Does it keep `core/router.py` from becoming a god object again?
* Does it preserve user trust (no wrong-answer reuse, no silent behavior change, no data loss)?
* Does it avoid fake feature claims (planned work is marked planned)?

Record a verdict: PASS, WARN, or FAIL. If the verdict is FAIL, stop and report rather than proceeding to commit or merge.

## Code simplicity gate (mandatory for code changes)

Every code change must pass the Code Simplicity Review before merge. Read `.claude/skills/code-simplicity-review/SKILL.md` before an implementation branch and run it with the `slop-hunter` agent before commit. The goal is small, boring, readable code; the gate fails AI slop (bloat, duplication, speculative abstractions, god objects). Full detail lives in the skill; the summary:

* Before coding: state the simplest implementation, why no larger abstraction is needed, files likely touched, files that must not be touched, and what "too much code" would look like for this task.
* During coding: edit existing seams over new systems; functions over classes unless state or a contract justifies one; one clear path; no speculative compatibility layers, config knobs, or public API; no vague manager/service/factory wrappers around simple logic.
* After coding: score Readability, Size, Duplication, Architecture, Long-term maintenance, Tests, and Slop detection as PASS, WARN, or FAIL, then run a final simplification pass (delete, inline, rename, simplify) and report what was removed and why the design is the simplest maintainable version.
* A FAIL blocks merge until resolved or explicitly accepted by the user. Skip only for trivial one-line or comment-only edits, and say you are skipping it and why.

## Task routing table (skills and reviewers)

Quick index. See "Routing matrix" and "Branch-to-agent routing (V2)" for full detail and confirmation rules. Reviewer names that were intentionally not created as agent files map to the closest committed agent inline, per "Branch-to-agent routing (V2)".

| Task type | Skills | Reviewers |
|-----------|--------|-----------|
| source / provider | model-source-design, system-design-review | principal-system-architect, provider-integration-reviewer, api-contract-architect, database-persistence-reviewer, qa-sdet-lead |
| routing policy | routing-policy-design, system-design-review | principal-system-architect, provider-integration-reviewer, behavior-preservation-checker, qa-sdet-lead |
| evals / scorecards | benchmark-scorecard-design | database-persistence-reviewer, behavior-preservation-checker, qa-sdet-lead |
| cache | cache-tier-design | embeddings-retrieval-reviewer, behavior-preservation-checker, database-persistence-reviewer, qa-sdet-lead |
| DB / persistence | system-design-review | database-persistence-reviewer, security-architect, behavior-preservation-checker, qa-sdet-lead |
| security / agent runtime | engineering-review-board | security-architect, agent-runtime-architect, behavior-preservation-checker, qa-sdet-lead |
| CLI / TUI | tui-product-experience-review | cli-interface-reviewer, behavior-preservation-checker, qa-sdet-lead |
| packaging / dependencies | dependency-slimming-review, implementation-plan-review | python-packaging-reviewer, behavior-preservation-checker, qa-sdet-lead |
| docs / release | readme-product-docs-review, product-direction-guard, release-readiness-review | slop-hunter, behavior-preservation-checker, qa-sdet-lead |

## Local and private instructions

This repository is public on GitHub. Keep tracked Claude files public-safe. Do not put private roadmap strategy, competitive analysis, large autonomous prompts, personal workflow details, secrets, or local paths into `CLAUDE.md`, `.claude/CLAUDE.md`, or any other tracked file.

Private or machine-local instructions (autonomous prompts, personal workflow, local paths) belong in `CLAUDE.local.md` at the repo root. It is git-ignored and must never be committed. If it does not exist you may create it locally; it stays local.

## Mandatory Implementation Gate

This gate is mandatory. Claude must clear every step before writing or editing any code or non-trivial file in this repo. No implementation begins until the gate is cleared.

1. Classify the task: feature, fix, refactor, docs, or recovery, in one or two sentences.
2. Classify risk: Low, Medium, or High, using the `agent-routing` scale.
3. Identify affected domains and the current branch's single concern. Confirm the work belongs on this branch per "Current active branch guidance"; if it does not, stop and re-scope.
4. Select the skill and reviewer agents from the original "Routing matrix" and the "Branch-to-agent routing (V2)" section.
5. State the behavior that must be preserved.
6. State the tests and checks to run, with specific files where possible.
7. For any High-risk task, or any item listed in "Stop conditions (V2)", stop and get explicit user confirmation before implementing.

Skipping the gate is allowed only for trivial, comment-only, or single-line docs edits, and you must say you are skipping it and why. When in doubt, run the gate. Agents are read-only reviewers; main Claude implements only after the gate is cleared and, where required, the user has confirmed.

## Product identity (V2)

* Orchestrator CLI is a local-first AI routing, benchmarking, and execution workbench for developers.
* One-line promise: benchmark local and cloud models on your own tasks, then route every prompt to the model that actually earned it based on quality, cost, latency, privacy, reliability, context, JSON support, tool support, and safety.
* The differentiator is benchmark-driven routing using the developer's own task sets and local scorecards. Not provider count. Not cache cleverness. Not a coding agent.
* What it is NOT: a generic AI gateway, a LiteLLM or OpenRouter clone, a hosted dashboard, a provider-count race, a general coding agent, or a plain cheapest-model router.
* Strategic truth to defend: as a generic API-key router, gateway, cache layer, or cost tracker, this project is a weaker version of products that already exist. The defensible niche is local-first, benchmark-driven routing across local and cloud model sources, scored on the user's own tasks.

## Current architecture (what exists today)

* CLI and TUI: Typer commands in `cli/commands/`, a Textual TUI in `cli/tui/` that runs the same workflows. The TUI shows real traces, cost, and status, not placeholders.
* Providers: connector plus adapter pairs for Anthropic, OpenAI, Groq, Gemini behind ABCs in `providers/base.py`. There is no `ModelSource` abstraction yet; the unit is provider plus account.
* Core router: `core/router.py` runs normalize, classify, build cache, lookup, estimate tokens, select cheapest-capable model, call provider, validate, store, write trace.
* Cache: exact-match SQLite cache only (see "Cache invariants"). `core/cache.py` is the backend selector (`ExactCache` or `NoOpCache`). The legacy semantic cache and the `embeddings/` package were removed.
* DB: SQLite via SQLAlchemy. Tables today are `connected_accounts`, `model_registry`, `traces`, `exact_cache`, `tool_calls`, and `cache_entries` (legacy semantic table, retained to preserve schema and old data; no longer written). No migrations. No vector store.
* Agent runtime: experimental ReAct loop in `agent/`, P0-hardened (subprocess env scrubbing, run_python/run_shell gated and not exposed unless enabled, tool-log redaction, sensitive-path denylist, write-overwrite protection). `allow_python` and `allow_shell` default off. `network_disabled` is advisory only, not enforced in source.
* Tests: `pytest` with `pytest-asyncio` and `pytest-mock`, plus `tests/tests_e2e_cli_simulation/`. No lint, format, or typecheck command exists.

## Strategic direction (future concepts)

These are the target domain concepts. None are implemented as DB models yet. Do not describe them as built.

* ModelSource: a registered source of models (local, cloud, OpenAI-compatible gateway, custom). Existing providers become one source type. Identity is the source, not a raw API key.
* RoutingPolicy: named policy of hard filters plus a scoring formula plus a fallback chain.
* TaskSet: a developer's own set of representative tasks with expected outputs or graders.
* BenchmarkRun: an execution of a TaskSet against selected models, producing measurements.
* Scorecard: per-model, per-task local results (quality, cost, latency, reliability, JSON/tool success) that feed routing.
* RoutingDecision: the chosen model plus the human-readable reasons it was chosen.
* FallbackPlan: the ordered alternatives if the primary model fails a hard filter or call.
* ExecutionTrace: a richer trace of a route or agent run, beyond today's flat `traces` row.

## Non-negotiable product rules

* Do not chase provider count. Breadth of providers is not the moat.
* Do not make manual API keys the product identity. Sources and scorecards are the identity.
* Do not reintroduce the heavy semantic cache (sentence-transformers + Qdrant). The exact cache is the only implemented cache; a lighter semantic-cache-v2 is future work and must stay opt-in, never the default.
* Do not promote agent mode as production-safe. P0 hardening has landed, but agent mode stays experimental until the `agent/safe-agent-mode` branch.
* Do not invent implemented features in docs, help text, or the TUI. Mark planned work as planned.
* Do not make heavy dependencies (`torch`, `sentence-transformers`, `qdrant-client`) required for base routing. Keep the default route path slim.
* Keep the local-first posture. No required hosted services, no telemetry by default.

## Branch discipline

* One branch equals one concern. No mega rewrites.
* Do not mix security, packaging, routing, source abstraction, evals, and TUI in one branch.
* Each branch follows: plan, implement, tests, review, merge.
* Each branch declares explicit out-of-scope and a definition of done. See `docs/roadmap/BRANCH_ROADMAP.md` and the `branch-migration-planning` skill.

## Accepted branch roadmap

1. `refactor/slim-deps-and-cache-tiers`: slim default deps, exact cache default, semantic optional. Cache tier code already landed on this concern; packaging extras are the remaining work.
2. `security/p0-agent-safety`: fix P0 agent-runtime security before any promotion of agent mode.
3. `docs/v2-product-direction` or `docs/claude-operating-system-v2`: docs and Claude support system aligned to V2 (this branch).
4. `fix/model-registry-integrity`: registry correctness, dedup, capability/pricing integrity.
5. `refactor/config-routing-seam`: clean the `core/router.py -> services/init_service` config coupling.
6. `architecture/model-source-abstraction`: introduce ModelSource, wrap existing providers behavior-preservingly.
7. `sources/openai-compatible-and-ollama`: add local and OpenAI-compatible sources.
8. `routing/policy-engine-v1`: hard filters, scoring, policies, fallback chains, route explanations.
9. `evals/benchmark-scorecards-v1`: TaskSet, BenchmarkRun, scoring, Scorecards that feed routing.
10. `design/tui-v2-workbench-experience`: TUI around sources, benchmarks, scorecards, routing, traces.
11. `cache/semantic-cache-v2`: build a lighter optional semantic cache to replace the removed v1 (candidates: sqlite-vec, provider embeddings, FastEmbed). Not implemented.
12. `agent/safe-agent-mode`: re-enable and promote agent mode only after P0 is fixed.

## Current active branch guidance

Read the branch name and constrain scope to that concern only:

* contains `slim-deps-and-cache-tiers`: only the cache and dependency path. No routing, schema, or provider behavior changes.
* contains `p0-agent-safety`: only agent-runtime security. No feature work.
* contains `docs` or `claude-operating-system`: only docs and the Claude support system. No application source, no `pyproject.toml`, no schema.
* contains `model-registry-integrity`: only registry data correctness.
* contains `config-routing-seam`: only the config coupling seam.
* contains `model-source`: only the ModelSource abstraction.
* contains `routing` or `policy`: only routing policy and scoring.
* contains `evals` or `benchmark`: only benchmarks and scorecards.
* contains `tui`: only TUI and product experience.
* contains `cache` (and not `slim-deps`): only the semantic cache backend.
* contains `agent` (and not `p0`): only safe agent mode, and only after P0 landed.

## Stop conditions (V2)

Stop and ask the user before any of these, regardless of branch:

* editing `pyproject.toml` when it was not the stated task.
* adding or removing a dependency.
* any DB schema change (no migration system exists).
* changing routing behavior or model selection.
* changing secrets, key handling, or token storage.
* promoting agent mode, or relaxing `allow_shell` or sandbox confinement.
* claiming a feature is implemented when it is planned.
* creating root-level report files, `.claude/reports/`, `_verify/`, or `.verify/`.
* tests fail outside the current task's scope.
* the selected skills or agents are missing and safety depends on them.
* a change would expose private or internal Claude workflow, or competitive or roadmap strategy, in a tracked file.
* `.claude/agents/**` would be committed, untracked, or modified outside a reviewed agent branch.
* a destructive Git action would be required (`git reset --hard`, `git clean`, force-push, deleting tracked files).
* the requested implementation conflicts with the product direction in "Product identity (V2)".

## Test commands (V2)

* `pip install -e ".[dev]"` then `pytest`. Async mode is auto; mocks via `pytest-mock`.
* `tests/tests_e2e_cli_simulation/` covers CLI behavior.
* There is no lint, format, or typecheck command. Do not invent one or claim one runs. If `pyproject.toml` later adds such tooling under an explicit packaging branch, update this line then.

## Review protocol (V2)

* Use the branch-to-agent routing below to pick reviewers by branch.
* Post-change review is required for non-trivial diffs.
* Behavior preservation is required for any refactor or cleanup that claims no behavior change.
* A qa bug hunt is required for risky changes (routing, cache correctness, persistence, agent runtime, benchmark scoring).
* Agents are read-only reviewers. Main Claude implements after approval.

## Branch-to-agent routing (V2)

The 14 reviewer agents under `.claude/agents/` are committed and canonical (formalized in `docs/review-agents-v1`). The V2-specific architect names referenced below (product-strategy-reviewer, model-source-architect, routing-policy-architect, benchmark-evals-architect, cache-architecture-reviewer, business-logic-reviewer, docs-product-positioning-reviewer, tui-product-designer, motion-interaction-reviewer, release-readiness-manager) were reviewed and intentionally NOT created: for a local single-user tool they would add review noise. Use the closest committed reviewer inline and apply the matching skill, for example: ModelSource / routing / benchmark work -> principal-system-architect + api-contract-architect + provider-integration-reviewer + qa-sdet-lead; release readiness -> qa-sdet-lead + behavior-preservation-checker; docs/positioning -> slop-hunter. Create a dedicated agent later only if a recurring need is proven.

* docs or README or product positioning:
  * skills: `readme-product-docs-review`, `product-direction-guard`
  * agents: product-strategy-reviewer, docs-product-positioning-reviewer, slop-hunter
  * confirmation: yes if positioning or claims change

* dependency slimming or cache tiers:
  * skills: `dependency-slimming-review`, `cache-tier-design`
  * agents: python-packaging-reviewer, cache-architecture-reviewer, embeddings-retrieval-reviewer, database-persistence-reviewer, qa-sdet-lead
  * confirmation: yes

* P0 agent security:
  * skills: `engineering-review-board`
  * agents: security-architect, agent-runtime-architect, qa-sdet-lead, behavior-preservation-checker
  * confirmation: yes

* ModelSource abstraction:
  * skills: `model-source-design`, `system-design-review`
  * agents: model-source-architect, provider-integration-reviewer, api-contract-architect, database-persistence-reviewer
  * confirmation: yes

* routing policy and scoring:
  * skills: `routing-policy-design`, `system-design-review`
  * agents: routing-policy-architect, business-logic-reviewer, provider-integration-reviewer (latency), qa-sdet-lead
  * confirmation: yes

* benchmarks and scorecards:
  * skills: `benchmark-scorecard-design`
  * agents: benchmark-evals-architect, database-persistence-reviewer, qa-sdet-lead
  * confirmation: yes

* TUI product experience:
  * skills: `tui-product-experience-review`
  * agents: tui-product-designer, cli-interface-reviewer, motion-interaction-reviewer, qa-sdet-lead
  * confirmation: yes if a workflow or output format changes

* release or merge readiness:
  * skills: `release-readiness-review`, `post-change-review`
  * agents: release-readiness-manager, behavior-preservation-checker
  * confirmation: this is the merge gate

* branch planning for any of the above:
  * skill: `branch-migration-planning`
  * confirmation: not applicable, planning only
