# Upgrade notes

Orchestrator CLI has no automatic database migration system. Your local data
lives under `~/.orchestrator/` (or `$ORCHESTRATOR_HOME`): `orchestrator.db`
(SQLite) and `config.toml`.

## To v0.2.0

**Database.** New tables introduced in v0.2 (the exact-match cache, task sets,
benchmark runs, and scorecards) are created automatically on first run.
`create_all` adds missing tables to an existing database without touching
existing data; it does not alter or migrate columns on tables that already
exist. v0.2 did not change any existing column, so a pre-0.2 database keeps
working: connected accounts, the model registry, and traces are preserved, and
the new tables are simply added.

**Cache.** `cache.mode = "semantic"` is no longer available; the legacy heavy
semantic cache (local embeddings plus an embedded vector store) was removed. Use
`cache.mode = "exact"` (the default) in `~/.orchestrator/config.toml`. Any old
`cache_entries` rows are left in place and ignored; you do not need to delete
them.

**Install.** The base install is slim and pulls no ML, vector, provider-SDK, or
TUI packages. Install only the extras you need, for example
`pip install -e ".[providers]"`, `".[tui]"`, or `".[all]"`. See the README
install section.

## If something looks wrong

Your data is local. Back up `~/.orchestrator/orchestrator.db`, then either keep
using it (the new tables are additive) or start clean by pointing
`ORCHESTRATOR_HOME` at a fresh directory and running `orchestrator init`.
