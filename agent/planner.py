"""Optional planning preamble for agent runs (static + cheap LLM hint)."""
from __future__ import annotations

from sqlalchemy.orm import Session

_STATIC = """\
Suggested workflow:
1. Use search_codebase or list_dir to locate relevant files.
2. read_file on the smallest set of files needed.
3. write_file to apply changes (stay within the sandbox).
4. run_python for quick checks or run_tests before finishing.
5. Summarize what you did in plain language when done.
"""


def plan_preamble(session: Session | None, goal: str, *, use_llm: bool = False) -> str:
    """
    Return text appended to the agent system prompt.
    If use_llm is True and session is set, ask the router for a short step list (cheap quality).
    """
    if not use_llm or session is None:
        return _STATIC
    try:
        from core.router import route
        from schemas.routing import RouteRequest

        prompt = (
            "You are a planning assistant. Given the user goal below, respond with a numbered "
            "list of 3–8 concrete steps (no tools). Be brief.\n\nGoal:\n"
            + goal[:2000]
        )
        result = route(
            RouteRequest(prompt=prompt, quality="cheap"),
            session,
        )
        text = (result.response_text or "").strip()
        if text:
            return "Plan (LLM-generated):\n" + text + "\n\n" + _STATIC
    except Exception:
        pass
    return _STATIC
