## Project Skills (Cursor Agent Skills)

This repository includes **project skills** to make common engineering workflows consistent and repeatable.

### Layout

Each skill lives in its own folder:

```
skills/
  <skill-name>/
    SKILL.md
```

### What a `SKILL.md` should include

- **When to use** (clear trigger conditions)
- **Goal / non-goals**
- **Step-by-step procedure** (no pseudocode)
- **Safety / constraints** (venv activation, sandbox bounds, no secret commits)
- **Examples** (good + bad, if relevant)

### Current skills

- `branch-pr-discipline`: branch → commit(s) → push → PR, with tests required
- `add-provider`: checklist for adding a provider connector/adapter + tests + docs

