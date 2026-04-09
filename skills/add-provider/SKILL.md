## Skill: Add a new provider (connector + adapter + tests + docs)

### When to use

Use this skill when adding a provider integration under `providers/<name>/` (including:
connector auth/validation/model discovery, `generate`, and optionally `chat_with_tools`).

### Goal

Add a provider such that:
- it can be **connected** (`orchestrator connect <provider>`)
- its models participate in **routing**
- behavior is covered by **tests** (no false greens)
- docs are updated (`README.md`, `CLAUDE.md`, `.env.example`)

### Procedure

1. **Scaffold**
   - Create `providers/<provider>/connector.py` implementing `BaseConnector`
   - Create `providers/<provider>/adapter.py` implementing `BaseAdapter.generate`
   - If agent tools are supported, implement `BaseAdapter.chat_with_tools`

2. **Wire into services/router**
   - Add provider to `services/connect_service.py`
   - Add adapter mapping in `core/router.py` (route path)
   - Add adapter mapping in `core/llm_turn.py` (agent path)
   - If tools are supported, add provider to `AGENT_TOOL_PROVIDERS`

3. **Update dependency spec**
   - Add SDK dependency to `pyproject.toml`
   - Ensure venv is active before installing anything

4. **Tests**
   - Add mocked tests verifying:
     - `validate_key` success/failure
     - `list_models` returns non-empty normalized rows
     - adapter `generate` parses response text + token usage
   - If tool calling is added:
     - add tests verifying tool call extraction and tool-result roundtrip mapping
     - update `test_llm_turn_providers.py` to include the new tool-capable provider in selection behavior

5. **Docs**
   - `README.md`: providers list, connect examples, architecture tree
   - `CLAUDE.md`: repository layout, agent/provider notes, out-of-scope adjustments
   - `.env.example`: add `<PROVIDER>_API_KEY` placeholder

6. **Run full suite**
   - `.\.venv\Scripts\python.exe -m pytest -q`

7. **Branch + PR**
   - Follow the “Branch → Commit → PR discipline” skill.

### Common failure modes to avoid

- Selecting a provider for agent tool rounds when `chat_with_tools` isn’t implemented
- Claiming a pip extra exists when it doesn’t
- “Fixing” failures by weakening assertions instead of matching real API behavior

