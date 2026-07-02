"""
Unified tool definitions for agent / function calling.

These use the OpenAI *wire shape* (type/function/name/parameters) as a neutral
contract. Each provider adapter translates the same list for its native API
(OpenAI & Groq: native; Anthropic: converted to tool + content blocks). The
orchestrator does **not** tie tools to a single vendor: ``agent_chat_turn`` and
the agent loop load **all** enabled models from **every** connected account,
then pick the cheapest tool-capable candidate (see ``core/llm_turn.py``).

Code-execution tools are NOT in the base list. ``run_python`` and ``run_shell``
are arbitrary code execution; they are only offered to the model when explicitly
enabled in agent config. Build the per-run list with :func:`agent_tools`.
"""
from __future__ import annotations

# Neutral JSON-schema parameters; adapters map this shape to each provider API.
# Base = safe-by-default tools only. No arbitrary code execution here.
AGENT_TOOLS_OPENAI: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file under the sandbox root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write UTF-8 text to a path under the sandbox root (creates parent dirs). Refuses to overwrite an existing file unless overwrite=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "overwrite": {"type": "boolean", "description": "Replace an existing file. Defaults to false."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List entries in a directory under the sandbox root.",
            "parameters": {
                "type": "object",
                "properties": {"directory": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_codebase",
            "description": "Search for a literal string under the sandbox (ripgrep or fallback).",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run pytest -q in the sandbox root.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# Opt-in, arbitrary-code-execution tools. Added only when explicitly enabled.
_RUN_PYTHON_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "run_python",
        "description": "Run a Python snippet with python -c under the sandbox cwd. Disabled unless enabled in agent config.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    },
}

_RUN_SHELL_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "run_shell",
        "description": "Run a shell command under the sandbox cwd. Disabled unless enabled in agent config; blocked-pattern filtered.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}


def agent_tools(*, allow_python: bool = False, allow_shell: bool = False) -> list[dict]:
    """Build the tool list for one agent run.

    Code-execution tools are appended only when explicitly enabled, so a model
    is never even offered ``run_python`` or ``run_shell`` by default.
    """
    tools = list(AGENT_TOOLS_OPENAI)
    if allow_python:
        tools.append(_RUN_PYTHON_TOOL)
    if allow_shell:
        tools.append(_RUN_SHELL_TOOL)
    return tools
