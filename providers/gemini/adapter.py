"""Google Gemini provider adapter."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from google.genai import types

from providers.base import AgentTurnResult, BaseAdapter, GenerateResult, ToolCallPart


def _openai_tools_to_gemini_tool(tools: list[dict[str, Any]]) -> types.Tool | None:
    decls: list[types.FunctionDeclaration] = []
    for t in tools:
        if t.get("type") != "function":
            continue
        f = t["function"]
        params = f.get("parameters") or {"type": "object", "properties": {}}
        decls.append(
            types.FunctionDeclaration(
                name=f["name"],
                description=f.get("description") or "",
                parameters_json_schema=params,
            )
        )
    if not decls:
        return None
    return types.Tool(function_declarations=decls)


def _openai_messages_to_gemini_contents(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[types.Content]]:
    """
    Map OpenAI-style chat (system / user / assistant / tool) to Gemini contents.
    Registers tool_call_id -> function name from assistant turns so tool rows can
    build FunctionResponse with a name (OpenAI tool messages omit name).
    """
    system_chunks: list[str] = []
    out: list[types.Content] = []
    tool_id_to_name: dict[str, str] = {}

    for m in messages:
        role = m.get("role")
        if role == "system":
            system_chunks.append(str(m.get("content") or ""))
            continue
        if role == "user":
            out.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=str(m.get("content") or ""))],
                )
            )
            continue
        if role == "assistant":
            parts: list[types.Part] = []
            if m.get("content"):
                parts.append(types.Part(text=str(m["content"])))
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                name = str(fn.get("name") or "")
                tc_id = str(tc.get("id") or "")
                if tc_id:
                    tool_id_to_name[tc_id] = name
                fc = types.FunctionCall(
                    id=tc_id or None,
                    name=name or None,
                    args=args,
                )
                parts.append(types.Part(function_call=fc))
            if not parts:
                parts.append(types.Part(text=""))
            out.append(types.Content(role="model", parts=parts))
            continue
        if role == "tool":
            tc_id = str(m.get("tool_call_id") or "")
            name = tool_id_to_name.get(tc_id) or ""
            raw = m.get("content")
            if isinstance(raw, str):
                try:
                    response_payload = json.loads(raw)
                except json.JSONDecodeError:
                    response_payload = {"output": raw}
            else:
                response_payload = {"output": str(raw)}
            if not isinstance(response_payload, dict):
                response_payload = {"output": str(response_payload)}
            fr = types.FunctionResponse(
                id=tc_id or None,
                name=name,
                response=response_payload,
            )
            out.append(
                types.Content(
                    role="user",
                    parts=[types.Part(function_response=fr)],
                )
            )
            continue

    system = "\n".join(system_chunks) if system_chunks else None
    return system, out


def _parse_turn_response(
    response: Any,
    *,
    model_id: str,
    latency_ms: int,
) -> AgentTurnResult:
    text_parts: list[str] = []
    tool_calls: list[ToolCallPart] = []
    finish_reason: str | None = None

    if response.candidates:
        cand = response.candidates[0]
        if cand.finish_reason is not None:
            finish_reason = str(cand.finish_reason)
        content = cand.content
        if content and content.parts:
            for i, part in enumerate(content.parts):
                if part.text:
                    text_parts.append(part.text)
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    name = str(getattr(fc, "name", None) or "")
                    args = getattr(fc, "args", None)
                    if not isinstance(args, dict):
                        args = {}
                    arguments_json = json.dumps(args)
                    fc_id = getattr(fc, "id", None)
                    tc_id = str(fc_id) if fc_id else f"gemini_fc_{i}_{uuid.uuid4().hex[:8]}"
                    tool_calls.append(
                        ToolCallPart(
                            id=tc_id,
                            name=name,
                            arguments_json=arguments_json,
                        )
                    )

    in_tok = out_tok = 0
    um = getattr(response, "usage_metadata", None)
    if um is not None:
        in_tok = getattr(um, "prompt_token_count", None) or 0
        out_tok = getattr(um, "candidates_token_count", None) or 0

    return AgentTurnResult(
        text="".join(text_parts),
        tool_calls=tool_calls,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
        model_id=model_id,
        provider="gemini",
        finish_reason=finish_reason,
    )


class GeminiAdapter(BaseAdapter):
    provider_name = "gemini"

    def generate(
        self,
        prompt: str,
        model_id: str,
        api_key: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> GenerateResult:
        from google import genai

        client = genai.Client(api_key=api_key)
        t0 = time.monotonic()
        model_ref = model_id if str(model_id).startswith("models/") else f"models/{model_id}"
        response = client.models.generate_content(
            model=model_ref,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        response_text = ""
        if response.text:
            response_text = response.text
        elif response.candidates:
            parts = response.candidates[0].content.parts
            response_text = "".join(
                getattr(p, "text", "") or "" for p in parts
            )
        in_tok = out_tok = 0
        um = getattr(response, "usage_metadata", None)
        if um is not None:
            in_tok = getattr(um, "prompt_token_count", None) or 0
            out_tok = getattr(um, "candidates_token_count", None) or 0
        return GenerateResult(
            response_text=response_text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            model_id=model_id,
            provider="gemini",
        )

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        model_id: str,
        api_key: str,
        tools: list[dict[str, Any]],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> AgentTurnResult:
        from google import genai

        client = genai.Client(api_key=api_key)
        model_ref = model_id if str(model_id).startswith("models/") else f"models/{model_id}"
        system, contents = _openai_messages_to_gemini_contents(messages)
        gemini_tool = _openai_tools_to_gemini_tool(tools)

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if system:
            config_kwargs["system_instruction"] = system
        if gemini_tool is not None:
            config_kwargs["tools"] = [gemini_tool]
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.AUTO,
                )
            )

        cfg = types.GenerateContentConfig(**config_kwargs)
        t0 = time.monotonic()
        response = client.models.generate_content(
            model=model_ref,
            contents=contents,
            config=cfg,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        return _parse_turn_response(
            response,
            model_id=model_id,
            latency_ms=latency_ms,
        )
