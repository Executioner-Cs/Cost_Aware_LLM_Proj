"""ReAct-style agent loop: LLM tool calls + sandboxed execution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from agent.config import load_agent_config
from agent.dispatcher import dispatch_tool
from agent.macro_expander import expand_macros, parse_goal_macros
from agent.sandbox import Sandbox
from core.llm_turn import agent_chat_turn
from schemas.tools import AGENT_TOOLS_OPENAI


def _system_prompt(sandbox_root: Path, max_iterations: int) -> str:
    return (
        f"You are a coding agent. All file paths must stay under the sandbox root:\n  {sandbox_root}\n"
        f"You may call tools to read, write, search, and run code. "
        f"Prefer minimal changes. You have at most {max_iterations} LLM turns; finish with a clear summary.\n"
        "Do not invent file paths; use list_dir or search_codebase first when unsure."
    )


def run_agent_loop(
    session: Session,
    goal: str,
    *,
    home: Optional[Path] = None,
    quality: str = "balanced",
    max_iterations: Optional[int] = None,
    use_plan: bool = False,
    plan_llm: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Run tool-using agent until the model returns text without tool calls or max iterations.

    Returns (final_text, conversation_messages).
    """
    from services.init_service import get_home

    h = home or get_home()
    acfg = load_agent_config(h)
    iterations = max_iterations if max_iterations is not None else acfg["max_iterations"]
    root = Path(acfg["sandbox_root"]).expanduser().resolve()
    sb = Sandbox(root=root, max_file_bytes=acfg["max_file_bytes"])

    parsed, stripped_goal = parse_goal_macros(goal)
    sys_text = _system_prompt(root, iterations)
    if parsed is not None:
        extra = expand_macros(parsed)
        if extra:
            sys_text += "\n\n" + extra
    if use_plan:
        from agent.planner import plan_preamble

        sys_text += "\n\n" + plan_preamble(session, stripped_goal, use_llm=plan_llm)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": sys_text},
        {"role": "user", "content": stripped_goal},
    ]

    for _ in range(iterations):
        turn = agent_chat_turn(
            session,
            messages,
            AGENT_TOOLS_OPENAI,
            quality=quality,
        )
        if not turn.tool_calls:
            return turn.text or "", messages

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments_json},
                }
                for tc in turn.tool_calls
            ],
        }
        if turn.text:
            assistant_msg["content"] = turn.text
        messages.append(assistant_msg)

        for tc in turn.tool_calls:
            res = dispatch_tool(
                tc.name,
                tc.arguments_json,
                sandbox=sb,
                session=session,
                allow_shell=acfg["allow_shell"],
                subprocess_timeout_sec=acfg["max_subprocess_seconds"],
                blocked_shell_patterns=acfg["blocked_shell_patterns"],
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(res),
                }
            )

    return "Stopped after maximum iterations without a final answer.", messages
