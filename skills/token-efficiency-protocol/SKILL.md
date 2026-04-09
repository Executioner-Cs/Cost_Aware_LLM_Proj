## Skill: Token-efficiency protocol (agent + routing)

### When to use

Use this skill whenever you:
- run multi-step `orchestrator agent` loops
- edit prompts/UX for `orchestrator route`
- update system prompts or anything that changes message volume

### Goal

Reduce tokens without reducing correctness by **designing communication protocols**, not relying on “be brief”.

### Core ideas (practical)

1. **Use compact envelopes**
   - Always communicate using a fixed small structure.
2. **Prefer diffs/state over raw logs**
   - Tool outputs get summarized; raw output only when needed.
3. **Keep a running state object**
   - Replace older turns with a compact state summary (goal/constraints/files/tests/next).
4. **Canonicalize prompts**
   - Consistent structure → higher semantic-cache hit rates.

### Recommended envelopes

#### Agent progress (one message)

```
State:
- Goal: <1 line>
- Constraints: <macros or 1–3 bullets>
- Files_touched: <list>
- Tests: <not_run | running | passed | failing: <summary>>
- Next: <1 line>
```

#### Tool output summary

```
ToolResultSummary:
- Tool: <name>
- Key_findings: <3 bullets max>
- Next_action: <1 bullet>
```

### Context compaction rules

When you receive long tool output:
- Keep **only**:
  - errors/failures
  - changed file paths
  - the minimal lines needed to act next
- Truncate everything else.

If `CX:<n>` is present (macro DSL):
- maintain a running state summary of ≤ `n` characters
- drop verbose narration; keep only actionable deltas

If `TOOLSUM:<n>` is present:
- summarize any single tool output to ≤ `n` characters

### Anti-patterns (wastes tokens)

- repeating the full repo purpose in every run
- pasting entire files when only a few lines matter
- adding redundant “acknowledgement” text
- re-running exploration steps without caching what you learned in the state object

### Checklist

- Is the agent re-reading files it already read? If yes, store the key lines in the state.
- Are we repeating constraints? If yes, use the macro DSL.
- Are tool outputs huge? If yes, summarize + keep only error lines / key diffs.

