"""
Unified tool definitions for agent / function calling.

These use the OpenAI *wire shape* (type/function/name/parameters) as a neutral
contract. Each provider adapter translates the same list for its native API
(OpenAI & Groq: native; Anthropic: converted to tool + content blocks). The
orchestrator does **not** tie tools to a single vendor: ``agent_chat_turn`` and
the agent loop load **all** enabled models from **every** connected account,
then pick the cheapest tool-capable candidate (see ``core/llm_turn.py``).
"""
from __future__ import annotations

# Neutral JSON-schema parameters; adapters map this shape to each provider API.
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
            "description": "Write UTF-8 text to a path under the sandbox root (creates parent dirs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
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
            "name": "run_python",
            "description": "Run a Python snippet with python -c under the sandbox cwd.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
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
