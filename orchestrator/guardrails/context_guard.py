"""Bound message history while preserving essential instructions and recent turns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from contract import ContextMetrics, MessageRecord
from orchestrator.utils.token_counting import TokenCounter


class ContextSummarizer(Protocol):
    def summarize(self, messages: Sequence[MessageRecord]) -> str: ...


@dataclass(frozen=True, slots=True)
class ContextGuardResult:
    messages: tuple[MessageRecord, ...]
    summary: str | None
    metrics: ContextMetrics


def manage_context(
    messages: Sequence[MessageRecord],
    *,
    token_limit: int,
    retain_recent: int,
    token_counter: TokenCounter,
    summarizer: ContextSummarizer,
) -> ContextGuardResult:
    """Prune obsolete outputs, summarize old history, and expose token metrics."""
    if token_limit <= 0:
        raise ValueError("token_limit must be positive.")
    if retain_recent < 1:
        raise ValueError("retain_recent must be at least one.")

    original = tuple(message.model_copy(deep=True) for message in messages)
    before_tokens = token_counter.count_messages(original)
    if before_tokens <= token_limit:
        return ContextGuardResult(
            messages=original,
            summary=None,
            metrics=ContextMetrics(
                before_tokens=before_tokens,
                after_tokens=before_tokens,
                pruned_messages=0,
                summarized_messages=0,
            ),
        )

    kept_after_obsolete = tuple(
        message
        for message in original
        if not (message.kind == "tool_output" and message.obsolete and not message.essential)
    )

    essential_indexes = {
        index for index, message in enumerate(kept_after_obsolete) if message.essential
    }
    nonessential_indexes = [
        index for index in range(len(kept_after_obsolete)) if index not in essential_indexes
    ]
    recent_indexes = set(nonessential_indexes[-retain_recent:])
    older_indexes = [index for index in nonessential_indexes if index not in recent_indexes]
    older_messages = [kept_after_obsolete[index] for index in older_indexes]

    summary: str | None = None
    summary_message: MessageRecord | None = None
    if older_messages:
        summary = summarizer.summarize(older_messages).strip()
        if not summary:
            raise ValueError("Context summarizer returned an empty summary.")
        summary_message = MessageRecord(
            role="assistant",
            kind="summary",
            essential=True,
            content=summary,
            name="context_manager",
        )

    kept_indexes = essential_indexes | recent_indexes
    compacted = [
        message for index, message in enumerate(kept_after_obsolete) if index in kept_indexes
    ]
    if summary_message is not None:
        insertion_index = next(
            (index for index, message in enumerate(compacted) if not message.essential),
            len(compacted),
        )
        compacted.insert(insertion_index, summary_message)

    # Hard cap: drop oldest nonessential recent turns until under the threshold.
    while token_counter.count_messages(compacted) > token_limit:
        removable = next(
            (
                index
                for index, message in enumerate(compacted)
                if not message.essential
            ),
            None,
        )
        if removable is None:
            break
        compacted.pop(removable)

    after_tokens = token_counter.count_messages(compacted)
    # Net delta against the untouched history. Obsolete removals are already
    # contained in it, because the partition, summarization, and hard-cap stages
    # all operate on the post-pruning list; adding the obsolete count on top
    # would double-count those messages. The delta is also net of the inserted
    # summary, so it trails the number of records physically dropped by one
    # whenever summarization runs.
    pruned_messages = len(original) - len(compacted)
    return ContextGuardResult(
        messages=tuple(compacted),
        summary=summary,
        metrics=ContextMetrics(
            before_tokens=before_tokens,
            after_tokens=after_tokens,
            pruned_messages=pruned_messages,
            summarized_messages=len(older_messages),
        ),
    )
