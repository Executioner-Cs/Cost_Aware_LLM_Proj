"""
Local macro-expander for token-efficient agent goals.

Users can prefix agent goals with an inline DSL block:

  {BRPR,VENV,NOFAKE,DOCSYNC,CX:2048,TOOLSUM:1K} Implement feature X

The block is expanded into additional system-prompt constraints, and removed
from the actual user goal. This avoids repeatedly spending tokens on the same
workflow constraints across runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_MACRO_BLOCK_RE = re.compile(r"^\s*\{(?P<body>[^}]*)\}\s*(?P<rest>.*)\s*$", re.DOTALL)


@dataclass(frozen=True)
class ParsedMacros:
    flags: frozenset[str]
    cx_chars: Optional[int] = None
    toolsum_chars: Optional[int] = None


def _parse_human_size(value: str) -> int:
    """
    Parse human-ish sizes like:
      2048, 2k, 2K, 1m
    Returned unit is characters (not bytes).
    """
    v = value.strip()
    if not v:
        raise ValueError("empty size")
    m = re.fullmatch(r"(?i)(\d+)\s*([km]?)", v)
    if not m:
        raise ValueError(f"invalid size {value!r}")
    n = int(m.group(1))
    suf = (m.group(2) or "").lower()
    mult = 1
    if suf == "k":
        mult = 1024
    elif suf == "m":
        mult = 1024 * 1024
    return n * mult


def parse_goal_macros(goal: str) -> tuple[ParsedMacros | None, str]:
    """
    If the goal begins with an inline macro block, parse it and return:
      (ParsedMacros, stripped_goal)
    Otherwise:
      (None, goal)
    """
    m = _MACRO_BLOCK_RE.match(goal or "")
    if not m:
        return None, goal

    body = (m.group("body") or "").strip()
    rest = (m.group("rest") or "").strip()

    flags: set[str] = set()
    cx_chars: Optional[int] = None
    toolsum_chars: Optional[int] = None

    if body:
        for raw in body.split(","):
            tok = raw.strip()
            if not tok:
                continue
            if ":" in tok:
                k, v = tok.split(":", 1)
                key = k.strip().upper()
                val = v.strip()
                if key == "CX":
                    cx_chars = _parse_human_size(val)
                elif key == "TOOLSUM":
                    toolsum_chars = _parse_human_size(val)
                else:
                    flags.add(f"{key}:{val}")
            else:
                flags.add(tok.upper())

    return ParsedMacros(flags=frozenset(flags), cx_chars=cx_chars, toolsum_chars=toolsum_chars), rest


def expand_macros(parsed: ParsedMacros) -> str:
    """
    Expand parsed macros into a compact constraint block appended to the agent system prompt.
    """
    lines: list[str] = []
    flags = parsed.flags

    if "BRPR" in flags:
        lines.append(
            "Workflow discipline (BRPR): use a feature branch; run real tests; commit in logical chunks; push and open a PR."
        )
    if "VENV" in flags:
        lines.append(
            "Venv discipline (VENV): activate `.venv` before installing deps or running tests; use `.venv`'s Python."
        )
    if "NOFAKE" in flags:
        lines.append(
            "No fake progress (NOFAKE): no pseudocode for runtime paths; no TODO placeholders for core behavior; tests must reflect reality."
        )
    if "DOCSYNC" in flags:
        lines.append(
            "Docs sync (DOCSYNC): update README.md (user-facing) and CLAUDE.md (canonical) when behavior/commands/architecture change."
        )

    if parsed.cx_chars is not None:
        lines.append(
            f"Context compaction (CX): keep conversational state concise; target ≤ {parsed.cx_chars} chars for the running state summary."
        )
    if parsed.toolsum_chars is not None:
        lines.append(
            f"Tool output compaction (TOOLSUM): summarize tool outputs; target ≤ {parsed.toolsum_chars} chars when pasting results back to the model."
        )

    if not lines:
        return ""

    return "Macro constraints:\n- " + "\n- ".join(lines)

