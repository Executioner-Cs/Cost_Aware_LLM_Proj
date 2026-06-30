# Orchestrator CLI

Local-first CLI to benchmark and route prompts across local and cloud LLMs by
cost and capability, with an exact-match cache and experimental sandboxed agent
tools. Single-user and local-first.

## Setup

* Python 3.11+
* Install: `pip install -e ".[dev]"`
* Test: `pytest`

There is no lint, format, or typecheck command.

## Contributing notes

* One branch, one concern. Keep changes small and reviewable.
* Never commit secrets or API keys. Provider keys load from the environment or a
  local `.env` (git-ignored); use `.env.example` as the template.
* Keep the base install light. Do not add heavy or unnecessary dependencies to
  the default path; provider SDKs and the TUI are optional extras.
* Do not claim features that are not implemented. Mark planned work as planned.

## Docs

* `README.md` for usage and install.
* `docs/` for architecture and decision records.

Machine-local Claude Code instructions, if you use any, belong in
`CLAUDE.local.md` at the repo root, which is git-ignored. See
`docs/development/CLAUDE_LOCAL_TEMPLATE.md` for a starting point.
