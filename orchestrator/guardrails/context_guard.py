"""Bound message history while preserving essential instructions and recent turns."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

from contract import ContextMetrics, MessageRecord
from orchestrator.utils.redaction import redact_payload
from orchestrator.utils.token_counting import TokenCounter

_LOGGER = logging.getLogger(__name__)


def is_safety_critical(message: MessageRecord) -> bool:
    """Records whose loss would be materially unsafe in the trading domain.

    A ``tool_output`` that has not been explicitly marked ``obsolete`` is a
    decision record: a fill, a compliance verdict, a risk-check outcome.
    ``obsolete`` stays the team's designated "safe to drop" signal, so this
    predicate adds protection without needing a contract change.
    """
    return message.kind == "tool_output" and not message.obsolete


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
    is_protected: Callable[[MessageRecord], bool] = is_safety_critical,
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

    prior_summary_indexes = {
        index
        for index, message in enumerate(kept_after_obsolete)
        if message.kind == "summary"
    }
    # Essential (system) and safety-critical records are both non-summarizable.
    # Prior summaries are deliberately excluded from this set: they are folded
    # into the next summary rather than accumulating one record per round. They
    # keep essential=True on the record itself, so the hard-cap loop can still
    # never evict one -- collapsing is not the same as making them droppable.
    essential_indexes = {
        index
        for index, message in enumerate(kept_after_obsolete)
        if (message.essential or is_protected(message))
        and index not in prior_summary_indexes
    }
    nonessential_indexes = [
        index
        for index in range(len(kept_after_obsolete))
        if index not in essential_indexes and index not in prior_summary_indexes
    ]
    recent_indexes = set(nonessential_indexes[-retain_recent:])
    older_indexes = [index for index in nonessential_indexes if index not in recent_indexes]
    older_messages = [kept_after_obsolete[index] for index in older_indexes]
    prior_summaries = [kept_after_obsolete[index] for index in sorted(prior_summary_indexes)]
    # Only re-summarize when there is genuinely new older material. Folding the
    # prior summaries in on an idle visit would burn an LLM call and degrade
    # fidelity for no compression gain.
    summarize_input = [*prior_summaries, *older_messages] if older_messages else []

    summary: str | None = None
    summary_message: MessageRecord | None = None
    if summarize_input:
        try:
            summary = summarizer.summarize(summarize_input).strip()
        except Exception as error:
            # The summarizer is the only network call in this guardrail. A
            # transient failure must not take the graph down: degrade to an
            # explicit elision marker so compression stays visible.
            # The summarizer is dependency-injected, so its exception text is
            # not under this module's control. The openai client in use does
            # not embed the request body in exception strings, but a different
            # client could, which would route the same history Diff 2 strips on
            # egress into the logs instead. Redact before logging.
            _LOGGER.warning(
                "Context summarizer failed (%s: %s); eliding %d older messages.",
                type(error).__name__,
                redact_payload(str(error)).payload,
                len(summarize_input),
            )
            summary = None
        if not summary:
            summary = (
                f"[{len(summarize_input)} older messages elided; "
                "summarizer unavailable]"
            )
        summary_message = MessageRecord(
            role="assistant",
            kind="summary",
            essential=True,
            content=summary,
            name="context_manager",
        )
        _LOGGER.info(
            "Context summarizer billed %d input tokens and %d output tokens.",
            token_counter.count_messages(summarize_input),
            token_counter.count_messages([summary_message]),
        )

    # A new summary supersedes the prior ones, so their indexes are dropped.
    # With no new summary, the prior summaries are carried through unchanged.
    kept_indexes = essential_indexes | recent_indexes
    if summary_message is None:
        kept_indexes |= prior_summary_indexes
    compacted = [
        message for index, message in enumerate(kept_after_obsolete) if index in kept_indexes
    ]
    if summary_message is not None:
        insertion_index = next(
            (index for index, message in enumerate(compacted) if not message.essential),
            len(compacted),
        )
        compacted.insert(insertion_index, summary_message)

    # Hard cap. Everything still present is essential, safety-critical, the
    # summary, or inside the protected recent window, so the only remaining
    # lever is evicting the OLDEST recent turns. The newest turn is never
    # dropped -- it is the turn the Coordinator is about to route on -- so this
    # can exit while still over budget rather than returning an empty history.
    while token_counter.count_messages(compacted) > token_limit:
        evictable = [
            index
            for index, message in enumerate(compacted)
            if not message.essential
            and not is_protected(message)
            and message.kind != "summary"
        ]
        if len(evictable) <= 1:
            _LOGGER.warning(
                "Context remains at %d tokens against a %d-token limit: the "
                "remaining %d message(s) are essential, safety-critical, the "
                "summary, or the newest turn.",
                token_counter.count_messages(compacted),
                token_limit,
                len(compacted),
            )
            break
        compacted.pop(evictable[0])

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
            summarized_messages=len(summarize_input),
        ),
    )
