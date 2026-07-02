"""Groq provider adapter — OpenAI-compatible Chat Completions."""
from __future__ import annotations

from providers.openai.adapter import OpenAIAdapter


class GroqAdapter(OpenAIAdapter):
    provider_name = "groq"
    _CHAT_BASE_URL = "https://api.groq.com/openai/v1"
