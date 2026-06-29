---
name: refactor-readability
description: Plan and review behavior-preserving readability refactors for Orchestrator CLI with domain-specific naming and explicit control flow, no hidden behavior changes, and required verification.
---

# refactor-readability

## Purpose

Behavior-preserving readability refactors. Make the code clearer without changing what it does, and prove the behavior is unchanged.

## When to use

* When clarity, naming, or structure is the goal and behavior must stay identical.
* Cleaning up known debt (for example the duplicated `_get_adapter` map in `core/router.py` and `core/llm_turn.py`, or long functions in `core/router.py`).
* Not for behavior changes; those go through implementation-plan-review and the review board.

## Required pre-read

* `.claude/CLAUDE.md` (readability standard, architecture expectations).
* The target code and the tests that pin its behavior.

## Required agents

* refactoring-readability-reviewer (lead).
* behavior-preservation-checker (always, to confirm no behavior change).
* slop-hunter when AI slop or dead code is suspected.
* refactor-test-strategist to pick the safety net when coverage is thin.

## Process

1. State the readability problem and the intended end state.
2. Identify the behavior that must be preserved and the tests or characterization checks that pin it.
3. Refactor rules to apply:
   * No clever one-liners for important logic.
   * No generic helper soup; helpers must earn their existence and have domain names.
   * No behavior changes hidden in cleanup.
   * Domain-specific naming over `data`, `obj`, `item`, `temp`, `result`.
   * Explicit control flow over dense expressions.
   * Comments explain why, not what.
4. Define the tests/checks required before and after.
5. Keep router, cache, provider, sandbox, and agent runtime code especially clear; treat these as high-risk to touch.

## Output format

```
Refactor target: <file:symbol>
Readability problem: <short>
Behavior to preserve: <list>
Proposed changes: <bullet list, mechanical and named>
Tests/checks: <commands and pytest files; gaps noted>
Risk: Low | Medium | High
Confirmation required: yes if high-risk code is touched
```

## Stop conditions

* Stop for user confirmation before refactoring high-risk code (router, cache, provider adapters, sandbox, agent loop).
* Stop if there is no test or characterization check to prove behavior is preserved; propose one first.
* Abort the refactor if it would change behavior; route it through implementation-plan-review instead.
* Do not edit code from this skill unless the user has approved the specific refactor.
