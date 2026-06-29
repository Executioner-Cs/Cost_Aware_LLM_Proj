---
name: code-simplicity-review
description: Keep Orchestrator CLI code changes small, boring, and readable, and fail AI slop (bloat, duplication, speculative abstractions, god objects). Read before every implementation branch, apply before commit, PASS required before merge.
---

# code-simplicity-review

## Purpose

Make code changes smaller, clearer, and easier for a human to maintain. Prevent code that technically works but is bloated, over-engineered, duplicated, or understandable only by its author.

## When to use

* Read before every implementation branch, during the Plan phase.
* Apply before commit on any code change.
* PASS is required before merge for any branch that changes code.
* Skip only for trivial one-line or comment-only edits, and say you are skipping it and why.

## Required pre-read

* This file.
* `.claude/agents/slop-hunter.md` (the reviewer role this gate runs).
* The files you intend to change, and the existing seams you could edit instead of adding a new system.

## Required agents

* slop-hunter (primary: AI slop, dead code, swallowed errors, doc drift).
* behavior-preservation-checker (any cleanup that claims no behavior change).
* principal-system-architect (boundary and abstraction questions).
* qa-sdet-lead (test focus and determinism).
* release-readiness (the merge gate; use the `release-readiness-review` skill).

## Process

### Before coding

1. Explain the simplest possible implementation.
2. Explain why a larger abstraction is not needed.
3. List files likely touched.
4. List files that must not be touched.
5. Define what "too much code" would look like for this task (the bloat you are watching for).

### During coding

1. Prefer editing existing seams over adding new systems.
2. Prefer functions over classes unless state or a contract justifies a class.
3. Prefer one clear path over multiple parallel paths.
4. Do not add compatibility layers unless required.
5. Do not add config knobs unless the user genuinely needs control.
6. Do not add new public API unless a future branch clearly needs it.
7. Do not hide simple logic behind vague manager, service, or factory abstractions.

### After coding: Code Simplicity Review

Answer PASS, WARN, or FAIL for each dimension, with a one-line reason.

1. Readability: can a human understand the change in one pass? Are names obvious? Are functions short enough? Is control flow straightforward?
2. Size: is the diff no larger than the problem deserves? Did we add files, classes, or helpers unnecessarily? Could any new code be deleted without losing behavior?
3. Duplication: did we duplicate logic? Did we create two ways to do the same thing? Did we leave old and new paths competing?
4. Architecture: did the change respect boundaries? cli/tui owns no business logic; services orchestrate; core owns routing logic; providers/sources own provider-specific behavior; db/repositories own persistence; docs do not claim future features as done.
5. Long-term maintenance: would a new developer understand this? Will it make the next roadmap branch easier? Did it remove debt rather than add debt?
6. Tests: are tests focused and readable? Do they prove behavior rather than implementation trivia? Are they deterministic? Are there no real API keys and no network calls?
7. Slop detection: FAIL the branch if any of these appear:
   * a giant catch-all helper
   * vague names like manager, helper, or handler without a clear reason
   * a speculative plugin system
   * a broad refactor mixed with feature work
   * many knobs or config flags without real need
   * repeated try/except blocks hiding errors
   * copied code with tiny changes
   * comments explaining confusing code instead of simplifying it
   * "temporary" code with no clear removal plan
   * route or core becoming a god object again

### Required final simplification pass

Before commit, look for code to delete, inline, rename, or simplify. Report:

* code deleted
* duplicate paths removed
* abstractions avoided
* why the final design is the simplest maintainable version

## Output format

```
Before-coding:
  simplest approach: <short>
  why no larger abstraction: <short>
  files likely touched: <list>
  files that must not be touched: <list>
  "too much code" looks like: <short>
Code Simplicity Review:
  Readability:           PASS | WARN | FAIL - reason
  Size:                  PASS | WARN | FAIL - reason
  Duplication:           PASS | WARN | FAIL - reason
  Architecture:          PASS | WARN | FAIL - reason
  Long-term maintenance: PASS | WARN | FAIL - reason
  Tests:                 PASS | WARN | FAIL - reason
  Slop detection:        PASS | WARN | FAIL - reason (list any slop found)
Final simplification pass:
  deleted: <list or none>
  duplicate paths removed: <list or none>
  abstractions avoided: <list or none>
  why simplest: <short>
Verdict: PASS | WARN | FAIL
```

## Stop conditions

Stop and report if:

* the simplest solution conflicts with existing architecture.
* cleanup would change behavior.
* code size grows more than expected.
* a new abstraction seems necessary but the reason is unclear.
* tests pass but the code is still hard to read.
* the branch introduces long-term debt.

Any FAIL blocks merge until it is resolved or explicitly accepted by the user. This is a review gate: do not edit code from this skill beyond the change under review.
