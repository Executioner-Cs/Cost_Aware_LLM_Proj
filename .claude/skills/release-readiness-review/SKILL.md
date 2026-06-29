---
name: release-readiness-review
description: Decide whether an Orchestrator CLI branch is mergeable. Enforces tests run or explicitly skipped with reason, docs updated when behavior changed, no source drift outside scope, no accidental dependency or schema changes, no secret exposure, and no unreviewed schema change.
---

# release-readiness-review

## When to use

* Before merging any branch.
* As the final gate after post-change-review.
* When asked "is this safe to merge."

## Goal

A clear merge or hold decision for a branch, based on tests, docs, scope discipline, and safety, not on whether the diff looks plausible.

## Non-goals

* Not the first-pass correctness review (post-change-review and domain agents do that).
* Not implementation. This is a gate.
* Does not relax the branch-scope or stop-condition rules in `.claude/CLAUDE.md`.

## Inputs required

* `git diff` and `git status` for the full branch against its base.
* The branch's definition of done from `docs/roadmap/BRANCH_ROADMAP.md` or its plan.
* The "Stop conditions (V2)" and "Current active branch guidance" sections of `.claude/CLAUDE.md`.

## Review steps

1. Tests: were they run? If skipped, is there an explicit, acceptable reason? Do they cover the changed behavior?
2. Docs: if behavior or commands changed, are README and docs updated to match?
3. Scope: does the diff stay within the branch's single concern? Flag any drift into another branch's territory.
4. Dependencies: any added, removed, or version-bumped dependency? Was it intended and approved?
5. Schema: any DB schema change? Was it reviewed, and does it have a migration story or accepted-risk note?
6. Secrets: any key, token, or `.env` content in code, logs, traces, or tests?
7. Definition of done: are all its criteria met and observable?

## Red flags

* Tests not run and no reason given, or tests weakened to pass.
* Behavior changed but docs untouched.
* Files changed that belong to a different branch's concern.
* A dependency or schema change that was not the stated task.
* Any secret material in the diff.
* Definition of done partially met but reported as complete.

## Output format

```
Branch: <name> vs <base>
Tests: run | skipped (reason) | missing for changed behavior
Docs: updated as needed? yes/no/n-a
Scope: in-scope | drift (files)
Dependency changes: none | intended | accidental (list)
Schema changes: none | reviewed+migration/accepted-risk | unreviewed
Secret exposure: none | found (file:line)
Definition of done: met | partial (gaps)
Decision: merge | hold
Reason: <short>
```

## Stop conditions

* Hold on any secret exposure, any unreviewed schema change, or any accidental dependency change.
* Hold if behavior changed without test coverage or without doc updates.
* Hold if the diff drifts outside the branch's single concern.
* Do not merge or edit from this skill; it issues the decision, a human or main Claude acts on it.

## Example invocation

"Run release-readiness-review on docs/claude-operating-system-v2 before merge."
