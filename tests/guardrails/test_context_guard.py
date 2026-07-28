from __future__ import annotations

from copy import deepcopy
from typing import Sequence

import pytest

from contract import MessageRecord
from orchestrator.guardrails.context_guard import manage_context
from orchestrator.utils.token_counting import ApproximateTokenCounter


class DeterministicSummarizer:
    def summarize(self, messages: Sequence[MessageRecord]) -> str:
        return f"Summary of {len(messages)} older messages."


def test_under_limit_preserves_messages_and_reports_metrics() -> None:
    messages = [MessageRecord(role="user", content="short message")]
    result = manage_context(
        messages,
        token_limit=100,
        retain_recent=2,
        token_counter=ApproximateTokenCounter(),
        summarizer=DeterministicSummarizer(),
    )
    assert list(result.messages) == messages
    assert result.metrics.before_tokens == result.metrics.after_tokens
    assert result.metrics.pruned_messages == 0


def test_over_limit_preserves_system_and_recent_turns() -> None:
    messages = [
        MessageRecord(role="system", content="Never execute real trades."),
        MessageRecord(
            role="tool",
            kind="tool_output",
            content="obsolete output " * 30,
            obsolete=True,
        ),
        *[
            MessageRecord(role="user", content=f"older turn {index} " * 20)
            for index in range(6)
        ],
        MessageRecord(role="assistant", content="recent answer " * 10),
        MessageRecord(role="user", content="recent question " * 10),
    ]
    snapshot = deepcopy(messages)
    result = manage_context(
        messages,
        token_limit=120,
        retain_recent=2,
        token_counter=ApproximateTokenCounter(),
        summarizer=DeterministicSummarizer(),
    )
    assert messages == snapshot
    assert any(message.role == "system" for message in result.messages)
    assert any(message.kind == "summary" for message in result.messages)
    assert all("obsolete output" not in message.content for message in result.messages)
    assert result.metrics.after_tokens < result.metrics.before_tokens
    assert result.metrics.summarized_messages > 0


def test_invalid_boundaries_are_explicit() -> None:
    with pytest.raises(ValueError):
        manage_context(
            [],
            token_limit=0,
            retain_recent=1,
            token_counter=ApproximateTokenCounter(),
            summarizer=DeterministicSummarizer(),
        )
    with pytest.raises(ValueError):
        manage_context(
            [],
            token_limit=10,
            retain_recent=0,
            token_counter=ApproximateTokenCounter(),
            summarizer=DeterministicSummarizer(),
        )
