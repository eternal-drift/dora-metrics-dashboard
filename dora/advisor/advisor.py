"""The Advisor: a thin agentic loop over dora.advisor.tools, driven by
Claude's tool runner. See dora/advisor/prompts.py for the guardrails this
loop depends on, and docs/roadmap.md for what's deliberately out of scope
for v0 (no vector-DB RAG, no streaming UI, no conversation persistence).
"""
from __future__ import annotations

import anthropic

from dora.advisor.prompts import SYSTEM_PROMPT
from dora.advisor.tools import ALL_TOOLS
from dora.config import settings


class Advisor:
    def __init__(self, model: str | None = None, max_tokens: int = 2048):
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. The AI Advisor needs an Anthropic API key -- "
                "see README.md."
            )
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = model or settings.advisor_model
        self._max_tokens = max_tokens

    def ask(self, question: str, history: list[dict] | None = None) -> tuple[str, list[dict]]:
        """Ask a question. Returns (answer_text, updated_history) so a caller
        (CLI, Streamlit) can keep a running conversation."""
        messages = list(history or [])
        messages.append({"role": "user", "content": question})

        runner = self._client.beta.messages.tool_runner(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            messages=messages,
        )

        last = None
        for message in runner:
            last = message
            messages.append({"role": "assistant", "content": message.content})
            tool_response = runner.generate_tool_call_response()
            if tool_response is not None:
                messages.append(tool_response)

        answer = ""
        if last is not None:
            answer = "\n".join(block.text for block in last.content if block.type == "text")
        return answer, messages
