---
name: dependency-slimming-review
description: Review dependency and optional-extras changes for Orchestrator CLI so base install stays light, heavy deps are optional and lazily imported, missing-extra errors are clean, and pyproject extras are accurate with no unplanned additions.
---

# dependency-slimming-review

## When to use

* Any change to `pyproject.toml` dependencies or optional extras.
* Any change that adds, moves, or lazily imports a dependency.
* Work on the `refactor/slim-deps-and-cache-tiers` concern.

## Goal

Keep the default route path free of heavy ML and vector dependencies. Make heavy capabilities optional, lazily imported, and accurately declared as extras, with clear errors when an extra is missing.

## Non-goals

* Not a cache correctness review (use cache-tier-design).
* Not a general packaging audit beyond the dependency story (python-packaging-reviewer covers build, scripts, wheel).
* Does not authorize adding new dependencies; new deps need explicit approval.

## Inputs required

* The diff to `pyproject.toml` and any import sites that changed.
* `core/cache.py` (backend selection and lazy import boundaries) and `embeddings/`.
* The "Cache invariants (tiered)" and "Non-negotiable product rules" sections of `.claude/CLAUDE.md`.

## Review steps

1. Confirm the default route path (`orchestrator route` with default config) imports no `torch`, `sentence-transformers`, or `qdrant-client`.
2. Confirm heavy imports happen lazily inside the function or backend that needs them, never at module import time.
3. Confirm optional extras in `pyproject.toml` are named, real, installable, and match what the code's missing-dependency errors tell users to install.
4. Confirm a missing extra raises a clear, actionable error (for example `MissingFeatureError` with an install hint), not an opaque ImportError or a silent fallback.
5. Confirm no new dependency was added without a stated need and approval.
6. Confirm base `requires-python` and markers are consistent.

## Red flags

* A top-level `import torch` or `import sentence_transformers` or `import qdrant_client` on the default path.
* An install hint that points to an extra that does not exist in `pyproject.toml`.
* A bare `try/except ImportError` that swallows the failure and silently degrades.
* A new heavy dependency added to base instead of an extra.
* Extras that overlap confusingly or are undocumented.

## Output format

```
Scope: pyproject.toml + import sites
Default-path purity: clean | heavy import found (file:line)
Lazy-import findings: <list or none>
Extras accuracy: <ok or mismatches between code hint and pyproject>
Missing-extra error quality: <clear | opaque | silent>
Unplanned dependency additions: <list or none>
Verdict: keep | fix | reject
Tests/checks recommended: <import-time check, install smoke check>
```

## Stop conditions

* Reject if the default path pulls a heavy dependency.
* Reject if an install hint references a non-existent extra.
* Stop and ask before approving any new dependency.
* Do not edit `pyproject.toml` or install packages from this skill.

## Example invocation

"Run dependency-slimming-review on the pyproject extras change for slim-deps."
