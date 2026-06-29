# Branch Roadmap

Status: accepted. One branch equals one concern. No mega rewrites. Each branch declares out-of-scope and a definition of done, and follows plan, implement, tests, review, merge.

The order below is the agreed sequence. A branch should not start work that belongs to a later branch.

---

## 1. refactor/slim-deps-and-cache-tiers

What it does: makes the default route path slim. Exact-match SQLite cache is the default and pulls no ML or vector dependencies. The semantic cache becomes opt-in with lazy heavy imports. Adds optional install extras so `torch`, `sentence-transformers`, and `qdrant-client` are not required for base routing.

Status note: the cache tier code (`core/cache.py`, router wiring, exact default, lazy semantic imports) has already landed on this concern. The remaining work is packaging: define and verify the optional extras in `pyproject.toml`, and make the install story match the code.

Out of scope: routing behavior, model selection, provider adapters, schema changes.

Definition of done: `orchestrator route` on a fresh base install imports no ML or vector packages. Optional extras install cleanly and the semantic mode works when they are present. Tests cover exact cache hit, miss, and TTL on read.

## 2. security/p0-agent-safety

What it does: fixes the P0 agent-runtime security gaps before agent mode is promoted. At minimum: enforce or honestly remove `network_disabled`, harden sandbox path confinement against symlink and absolute-path escape, and confirm `allow_shell` defaults and blocked patterns are effective.

Out of scope: new agent features, new tools, performance.

Definition of done: every documented agent safety property is either enforced in source or removed from the docs. Sandbox escape tests pass. No secret can reach logs or traces.

## 3. docs/v2-product-direction (or docs/claude-operating-system-v2)

What it does: aligns README, docs, `.claude/CLAUDE.md`, skills, and agents to the V2 product direction. Documentation and Claude support system only.

Out of scope: application source, `pyproject.toml`, schema, provider adapters, router behavior.

Definition of done: README and docs describe the product honestly with a clear current-vs-planned split. `.claude/CLAUDE.md` carries the V2 direction. Skills and agents know the new direction. No application source touched.

## 4. fix/model-registry-integrity

What it does: corrects model registry data integrity: dedup on re-sync, capability flag accuracy, pricing sanity, and discovery fallbacks that do not silently hide failure.

Out of scope: ModelSource abstraction, routing policy.

Definition of done: re-syncing an account does not duplicate rows. Capability flags and prices are consistent across dataclass, ORM, and selector. Fallbacks are visible.

## 5. refactor/config-routing-seam

What it does: cleans the known `core/router.py -> services/init_service` config coupling so the router does not pull config through a service.

Out of scope: behavior changes. This is a behavior-preserving refactor.

Definition of done: the coupling is removed or clearly isolated, behavior is provably unchanged, and tests pin the routing path.

## 6. architecture/model-source-abstraction

What it does: introduces the ModelSource abstraction. Existing providers are wrapped as one source type, behavior-preservingly. Sets up local, cloud, gateway, and custom source types.

Out of scope: adding new sources (that is the next branch), routing policy.

Definition of done: existing provider routing works unchanged through the new abstraction. The abstraction supports more than one source type without a provider-count chase.

## 7. sources/openai-compatible-and-ollama

What it does: adds local and OpenAI-compatible model sources (Ollama and OpenAI-compatible endpoints) on top of the ModelSource abstraction.

Out of scope: routing policy, benchmarks.

Definition of done: a local model and an OpenAI-compatible endpoint can be registered as sources and routed to, with privacy or local-only treated as a real attribute.

## 8. routing/policy-engine-v1

What it does: builds the routing policy engine: hard filters, a scoring formula, named policy modes, fallback chains, and route explanations. Cheapest capable, not cheapest overall. Quality floor, privacy and local policy, and context, tool, and JSON hard filters.

Out of scope: benchmark data production (consumes scorecards when present, works without them).

Definition of done: routing applies hard filters then scoring, produces a fallback chain, and explains why the chosen model won.

## 9. evals/benchmark-scorecards-v1

What it does: builds TaskSet, BenchmarkRun, exact and JSON scoring, scorecards, and the link from scorecards into routing. Exact deterministic scoring first; LLM-as-judge only where needed and never treated as ground truth.

Out of scope: large judge frameworks, hosted eval services.

Definition of done: a developer can define a TaskSet, run it across models, get local scorecards, and have routing consume them. Sample size is visible. Judge scores are labeled as judge scores.

## 10. design/tui-v2-workbench-experience

What it does: reshapes the TUI around the product mental model: sources, benchmarks, scorecards, routing, traces. Keyboard-first terminal UX. Honest placeholders for anything not yet implemented.

Out of scope: new backend behavior, fake metrics.

Definition of done: the TUI reflects the real workflow, marks unimplemented areas clearly, and warns that agent mode is experimental. Motion is subtle and only where useful.

## 11. cache/semantic-cache-v2

What it does: hardens and improves the optional semantic cache: TTL on lookup, long-prompt safety, store-drift handling between SQLite and Qdrant.

Out of scope: making semantic the default. It stays optional.

Definition of done: semantic TTL is enforced or explicitly documented as not, long-prompt unsafe hits are prevented, and SQLite-Qdrant drift is handled or surfaced.

## 12. agent/safe-agent-mode

What it does: re-enables and promotes agent mode only after P0 safety is fixed. Adds whatever gating, confirmation, and isolation the safety review requires.

Out of scope: anything that runs before branch 2 is merged.

Definition of done: agent mode is safe to run on a real repository, documented honestly, and its safety properties are enforced in source.
