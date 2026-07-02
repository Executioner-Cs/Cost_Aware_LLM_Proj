# Next steps

Public, high-level follow-ups after v0.2.0. These are directional and may change. See `CHANGELOG.md` for what actually ships and `docs/product/OVERVIEW.md` for the current product summary.

- **Source-qualified model identity.** Distinguish same-named models from different local or custom sources so they do not collide in the registry.
- **Upgrade guidance.** Document how to move a pre-0.2 local database forward; there is no automatic migration system, so the path is currently manual.
- **Provider catalog resilience.** More honest discovery fallback, retry and backoff on transient provider errors, and clearer handling of pricing and capability drift.
- **Local source testing.** Expand smoke coverage for local and OpenAI-compatible sources using a mock or optional local environment, without requiring real endpoints or keys in CI.
- **Routing dimensions.** Make latency and reliability live routing factors once benchmarks record them.
- **Init summary accuracy.** The `orchestrator init` summary should describe only what the default (exact) mode actually creates (config and database), not a vector store or an embedding-model download.
- **Lightweight semantic cache (deferred).** Any future semantic cache must be opt-in and lightweight, with no heavy ML or vector dependencies and no base-install growth. It is not planned until such a design is justified.
