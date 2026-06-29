---
name: qa-bug-hunt
description: Hunt bugs and regression risks in Orchestrator CLI across critical flows, edge cases, security, CLI, provider failures, persistence, and retrieval quality, with concrete regression test suggestions.
---

# qa-bug-hunt

## Purpose

Find bugs and regression risks. Map the critical flows, attack the edges, and propose the minimum tests that would have caught each issue.

## When to use

* When asked to find bugs or assess regression risk.
* As part of post-change-review for logic changes.
* Before a change to a high-risk path is approved.

## Required pre-read

* `.claude/CLAUDE.md` (high-risk areas, invariants).
* The target code and its existing tests (`tests/`, `tests/tests_e2e_cli_simulation/`).
* `git diff` when reviewing a change.

## Required agents

This skill is usually driven by qa-sdet-lead and pulls in domain agents (security-architect, provider-integration-reviewer, embeddings-retrieval-reviewer, database-persistence-reviewer, cli-interface-reviewer, agent-runtime-architect) for their areas.

## Process

Work through each class of risk and record concrete findings:

1. Critical flow mapping: trace the route pipeline (`core/router.py`), agent loop (`agent/loop.py`), connect/discovery, and cache read/write end to end.
2. Edge cases: empty prompts, oversized prompts and files, missing models, no connected accounts, malformed config.
3. Negative tests: invalid input, decryption failure, provider HTTP errors, JSON parse failure in `json_extract`.
4. Security cases: secret in logs, sandbox escape via symlink or absolute path, untrusted tool output steering the agent.
5. CLI cases: destructive commands without confirmation, wrong exit codes, TUI vs CLI divergence.
6. Provider failure cases: timeouts, non-200 responses, silent fallback to hardcoded models, capability-flag mismatch.
7. Database persistence cases: dual-store drift (SQLite vs Qdrant), cascade delete correctness, no-migration schema risk, transaction boundaries.
8. Embeddings/retrieval quality cases: threshold edges, wrong-answer reuse, task_type/quality filter bypass, TTL configured but not enforced.
9. Regression test suggestions: name the specific pytest file and case to add for each finding.

## Output format

```
Critical flows checked: <list>
Findings:
  - [severity] file:symbol — issue — why it matters — repro or reasoning
Test gaps: <list>
Suggested regression tests: <pytest file::case with one-line intent>
Confirmed vs assumed: <split>
```

## Stop conditions

* Flag and stop on any confirmed secret exposure or sandbox escape; escalate to security-architect.
* Do not claim a flow is safe without tracing it or citing a test.
* Do not write or run tests from this skill unless the user explicitly asks; suggest them.
* Do not edit code.
