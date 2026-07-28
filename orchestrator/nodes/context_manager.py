"""Global context-management node executed before each Coordinator visit."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from contract import AgentState, MessageRecord
from orchestrator.guardrails.context_guard import ContextSummarizer, manage_context
from orchestrator.utils.token_counting import TokenCounter

NodeCallable = Callable[[AgentState], dict[str, object]]


class LangChainContextSummarizer:
    def __init__(self, chat_model: Any) -> None:
        self._chat_model = chat_model

    def summarize(self, messages: Sequence[MessageRecord]) -> str:
        joined = "\n".join(f"{message.role}: {message.content}" for message in messages)
        response = self._chat_model.invoke(
            "Summarize the older orchestrator history in under 120 words, "
            "preserving decisions, errors, and identifiers:\n" + joined
        )
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            raise TypeError("Context summarizer returned non-text content.")
        return content


def make_context_manager_node(
    *,
    token_counter: TokenCounter,
    summarizer: ContextSummarizer,
    token_limit: int,
    retain_recent: int,
) -> NodeCallable:
    def context_manager_node(state: AgentState) -> dict[str, object]:
        result = manage_context(
            state.messages,
            token_limit=token_limit,
            retain_recent=retain_recent,
            token_counter=token_counter,
            summarizer=summarizer,
        )
        return {
            "messages": list(result.messages),
            "context_summary": result.summary or state.context_summary,
            "context_metrics": result.metrics,
        }

    return context_manager_node
