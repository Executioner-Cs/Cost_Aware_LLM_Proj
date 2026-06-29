---
name: cache-tier-design
description: Guide and review the tiered cache for Orchestrator CLI. Enforces exact cache as default, semantic cache optional, no wrong-answer reuse, no unsafe long-prompt semantic hits, no hidden SQLite/Qdrant drift, and no create_all column-migration myths.
---

# cache-tier-design

## When to use

* Any change to `core/cache.py`, `core/semantic_cache.py`, cache config, or cache CLI behavior.
* Designing TTL, backend selection, or store layout for the cache.
* Work on `refactor/slim-deps-and-cache-tiers` or `cache/semantic-cache-v2`.

## Goal

Keep the cache correct and tiered: exact-match SQLite as the safe default, semantic as an optional backend, with correctness always ahead of hit rate.

## Non-goals

* Not a dependency/extras review (use dependency-slimming-review).
* Not embedding model quality tuning (embeddings-retrieval-reviewer owns retrieval quality).
* Does not make semantic the default. It stays optional.

## Inputs required

* `core/cache.py` (`get_cache`, `ExactCache`, `NoOpCache`, `SemanticCacheBackend`).
* `core/semantic_cache.py` and `db/models.py` (`ExactCacheEntry`, `cache_entries`).
* The "Cache invariants (tiered)" section of `.claude/CLAUDE.md`.

## Review steps

1. Confirm `get_cache` defaults to exact and that unknown modes fall back to exact, not semantic.
2. Confirm an exact hit can only return the same prompt's answer at the same task_type and quality.
3. Confirm a semantic hit requires all three: similarity above threshold, exact task_type, exact quality.
4. Check TTL: exact cache enforces on read; document whether semantic enforces on lookup, and call out the gap if not.
5. Check long-prompt safety for semantic: two long prompts that differ only in a pasted document can embed as near-identical. Confirm this cannot produce a wrong-answer hit.
6. Check store consistency: the semantic path writes SQLite then Qdrant with no spanning transaction. Confirm drift is handled or surfaced, not hidden as success.
7. Confirm `create_all` is not treated as a migration tool. It creates missing tables only; it does not add or alter columns on an existing table.

## Red flags

* Default flipping to semantic, or unknown config falling through to semantic.
* A similarity threshold lowered without tests on nearby-but-wrong prompt pairs.
* Semantic TTL silently unenforced while presented as enforced.
* A long-prompt pair that collides on embedding and serves the wrong answer.
* A partial dual-store write reported as a successful store.
* Relying on `create_all` to migrate a changed column.

## Output format

```
Scope: <files>
Default-tier check: <exact default confirmed? yes/no>
Correctness findings:
  - [severity] file:symbol: issue, correctness impact
TTL findings: <exact vs semantic>
Long-prompt safety: <ok or risk>
Store-consistency findings: <drift handling>
Migration-myth check: <create_all used correctly? yes/no>
Verdict: keep | fix | reject
Tests/checks recommended: <pytest files, e.g. test_exact_cache.py>
```

## Stop conditions

* Reject any change that enables wrong-answer reuse on either tier.
* Reject a threshold reduction without tests for nearby-but-wrong prompts.
* Reject any reliance on `create_all` to migrate columns; require an explicit accepted-risk note or a real migration story.
* Do not edit code or touch the live DB from this skill.

## Example invocation

"Use cache-tier-design to review the semantic TTL change before merge."
