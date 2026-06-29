---
name: benchmark-scorecard-design
description: Guide TaskSet, BenchmarkRun, scoring, and Scorecard design for Orchestrator CLI. Enforces exact deterministic scoring first, LLM-as-judge only when needed and never as ground truth, visible sample size, local task-specific scorecards, and results that feed routing.
---

# benchmark-scorecard-design

## When to use

* Designing or reviewing the `evals/benchmark-scorecards-v1` branch.
* Any change to task sets, benchmark execution, scoring, or scorecards.
* Any work that connects benchmark results into routing.

## Goal

A local benchmarking loop: define a TaskSet, run it across models, score deterministically where possible, and produce per-model per-task Scorecards that feed routing. Trustworthy measurement over impressive numbers.

## Non-goals

* Not the routing policy itself (use routing-policy-design); this produces the data the policy consumes.
* Not a hosted eval service. Everything is local.
* Not a leaderboard. Scorecards are the user's own, task-specific.

## Inputs required

* The TaskSet, BenchmarkRun, and Scorecard concepts in `docs/architecture/ORCHESTRATOR_V2_ARCHITECTURE.md`.
* `db/models.py` (new tables will be needed; no migration system exists).
* The "Non-negotiable product rules" section of `.claude/CLAUDE.md`.

## Review steps

1. Confirm exact and deterministic scoring comes first: exact match, JSON or schema validity, numeric tolerance, where the task allows it.
2. Confirm LLM-as-judge is used only where deterministic scoring cannot apply, and that judge scores are clearly labeled as judge scores, not ground truth.
3. Confirm sample size is recorded and visible, so a scorecard built on three tasks is not read as authoritative.
4. Confirm scorecards are local and task-specific, stored per model and per task with quality, cost, latency, reliability, and JSON or tool success.
5. Confirm benchmark results feed routing in a defined way (which fields the policy reads).
6. Confirm reproducibility: the same TaskSet and models produce comparable runs, and runs are timestamped and inspectable.
7. Confirm new DB tables have a migration story or an explicit accepted-risk note.

## Red flags

* LLM-as-judge presented as ground truth or used where exact scoring would work.
* Sample size hidden, so tiny benchmarks look authoritative.
* A single aggregate score with no per-task breakdown.
* Scorecards that do not actually connect to routing.
* Non-deterministic scoring with no seed or tolerance, reported as exact.
* New schema with no migration or accepted-risk note.

## Output format

```
Scope: <files>
Scoring order: exact/JSON first, judge only as needed? yes/no
Judge labeling: judge scores marked as non-ground-truth? yes/no
Sample size: recorded and visible? yes/no
Scorecard shape: per-model per-task, local, with quality/cost/latency/reliability/JSON-tool? 
Routing linkage: which scorecard fields feed routing?
Reproducibility: runs comparable, timestamped, inspectable? yes/no
Schema/migration note: <story or accepted-risk>
Verdict: keep | fix | reject
Required reviewers: benchmark-evals-architect, database-persistence-reviewer, qa-sdet-lead
```

## Stop conditions

* Reject if judge scores are treated as ground truth or replace feasible deterministic scoring.
* Reject if sample size is hidden or scorecards do not feed routing.
* Reject new schema with no migration story or accepted-risk note.
* Do not edit code from this skill.

## Example invocation

"Apply benchmark-scorecard-design to the BenchmarkRun and scoring proposal."
