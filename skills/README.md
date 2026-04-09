## Project Skills (Cursor Agent Skills)

This repo ships **project skills** as Markdown so contributors (human or agent) can follow the same high-signal workflows without re-explaining constraints every time.

### Layout

```
skills/
  <skill-name>/
    SKILL.md
```

### What a `SKILL.md` must include

- **When to use** (clear triggers)
- **Goal / non-goals**
- **Inputs / outputs** (if relevant)
- **Step-by-step procedure** (no pseudocode for runtime paths)
- **Safety + constraints** (venv discipline, sandbox bounds, secrets, branch/PR discipline)
- **Examples** (minimum prompts, macro usage, failure recovery)

### Skills in this repo

- `token-efficiency-protocol` — context compaction, minimal envelopes, state format
- `macro-hand-sign-dsl` — inline `{...}` macros used by `orchestrator agent`
- `cache-safety-playbook` — correctness guardrails for semantic cache
- `strict-workflow` — branch→commit→push→PR discipline with real tests

