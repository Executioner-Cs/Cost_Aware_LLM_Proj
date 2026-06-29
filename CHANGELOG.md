# Changelog

All notable changes to Orchestrator CLI are recorded here. This project follows
[Semantic Versioning](https://semver.org/).

## 0.2.0

Local-first AI routing and benchmarking workbench. The release theme is
benchmark-driven routing on your own task sets, a slimmer default install, and
honest scoping of what is implemented versus planned.

### Added

- **Model sources.** Local Ollama and OpenAI-compatible HTTP endpoints can be
  connected alongside the cloud providers (`connect <provider> --base-url URL`,
  `connect ollama` keyless). Routing and benchmarking run through one
  `ModelSource` seam (`providers/source.py`).
- **Benchmarks and scorecards.** Build your own task sets and score models on
  them locally: `benchmark create`, `add-task`, `run`, `scorecards`. Grading is
  deterministic only (exact / contains / json_valid); no LLM-as-judge, no hosted
  service. Results persist to local SQLite (`task_sets`, `benchmark_tasks`,
  `benchmark_runs`, `scorecards`).
- **Routing policy engine.** Named policies with hard filters and a scoring
  formula, plus route explanations and a fallback chain (`core/policy.py`).
  Policies: `default`/`cheapest`, `privacy-first`, `quality-first`, `benchmarked`.
- **Scorecard-aware routing (opt-in).** The `benchmarked` policy prefers models
  that scored well on your task sets, with an explicit fallback to cheapest when a
  model has no scorecard: `route "<prompt>" --policy benchmarked [--task-set S]`.
  The default route is unchanged (cheapest capable).
- **TUI workbench.** The immersive TUI reaches parity with the CLI for the
  workbench: `benchmark` commands, `route --policy/--task-set`, and
  `connect --base-url` for local sources.

### Changed

- **Slim default install.** Base routing, the exact-match cache, persistence, and
  the CLI run on a light dependency set. Provider SDKs, the Textual TUI, and any
  future semantic cache are optional extras, loaded lazily only when used.
- **Account = source identity.** Account sync is source-aware: cloud accounts
  validate the stored key via their connector (unchanged); local and
  OpenAI-compatible accounts re-discover models through their source.
- **Package metadata** corrected: the description no longer claims "semantic
  caching" (none is implemented) and reflects the benchmark-and-route identity.

### Security

- **Experimental agent hardening.** Expanded the sandbox credential denylist
  (matched on components below the sandbox root), broadened destructive
  shell-pattern defaults, widened tool-log secret redaction (more provider key
  shapes, full PEM blocks) and removed a super-linear redaction edge case, and
  the agent CLI now prints an explicit experimental, not-production-safe warning
  (network access is not isolated). `allow_shell`/`allow_python` remain off by
  default; agent mode stays experimental.

### Removed

- The legacy heavy semantic cache (sentence-transformers + Qdrant) and the
  `embeddings/` package. The exact-match SQLite cache is the only implemented
  cache. A lighter optional semantic cache (`semantic-cache-v2`) is planned but
  not implemented.

### Not yet implemented (planned)

- A lighter opt-in semantic cache (`semantic-cache-v2`).
- Source-qualified model identity (so two local endpoints exposing the same model
  name do not collide in the registry).
- Latency and reliability as live routing dimensions (declared, scored neutrally
  until benchmarks record them).

## 0.1.0

- Initial Orchestrator CLI: cost-aware routing across Anthropic, OpenAI, Groq, and
  Gemini; exact-match SQLite cache; encrypted account storage; routing traces;
  Typer CLI and Textual TUI; experimental sandboxed ReAct agent tools.
