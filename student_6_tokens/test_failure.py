"""Deterministic context-window growth failure reproduction."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from contract import MessageRecord
from snippet import ApproximateTokenCounter, manage_context


class DeterministicSummarizer:
    def summarize(self, messages: Sequence[MessageRecord]) -> str:
        return f"Summary preserving {len(messages)} older decisions and errors."


def build_messages() -> list[MessageRecord]:
    return [
        MessageRecord(role="system", content="Never execute real trades."),
        MessageRecord(
            role="tool",
            kind="tool_output",
            content="obsolete tool output " * 40,
            obsolete=True,
        ),
        *[
            MessageRecord(role="user", content=f"historical turn {index} " * 30)
            for index in range(10)
        ],
        MessageRecord(role="assistant", content="recent decision " * 15),
        MessageRecord(role="user", content="recent validation question " * 15),
    ]


def main() -> None:
    messages = build_messages()
    counter = ApproximateTokenCounter()
    without_tokens = counter.count_messages(messages)
    result = manage_context(
        messages,
        token_limit=180,
        retain_recent=2,
        token_counter=counter,
        summarizer=DeterministicSummarizer(),
    )

    print("=== WITHOUT GUARDRAIL ===")
    print(f"Messages retained: {len(messages)}")
    print(f"Estimated input tokens: {without_tokens}")
    print("Obsolete tool outputs retained: 1")

    print("\n=== WITH GUARDRAIL ===")
    print(f"Messages retained: {len(result.messages)}")
    print(f"Estimated input tokens: {result.metrics.after_tokens}")
    print(f"Messages summarized: {result.metrics.summarized_messages}")
    print(f"Messages pruned: {result.metrics.pruned_messages}")

    print("\n=== METRICS ===")
    reduction = 100 * (without_tokens - result.metrics.after_tokens) / without_tokens
    print(f"Estimated token reduction: {reduction:.1f}%")
    print("System instructions preserved: true")

    assert result.metrics.after_tokens < without_tokens
    assert any(message.role == "system" for message in result.messages)
    assert all("obsolete tool output" not in message.content for message in result.messages)


if __name__ == "__main__":
    main()
