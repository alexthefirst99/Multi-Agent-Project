from __future__ import annotations

from copy import deepcopy
from typing import Sequence

from contract import AgentState, ContextMetrics, MessageRecord
from orchestrator.nodes.context_manager import make_context_manager_node
from orchestrator.utils.token_counting import ApproximateTokenCounter

SYSTEM_INSTRUCTION = (
    "Never execute real trades. Every order placement, cancellation, and "
    "compliance alert is mocked and must be logged to the audit trail."
)
STALE_ORDER_BOOK = (
    "Level-2 snapshot NVDA 09:31:04 bid 118.41x1200 118.40x900 118.39x2400 "
    "ask 118.44x800 118.45x1500 118.46x3100 sequence 88214 "
) * 8
ORDER_PAYLOAD = (
    '{"tool_name": "execute_trade", "arguments": {"ticker": "NVDA", '
    '"side": "buy", "quantity": 250}}'
)
COMPLIANCE_CHECK = (
    "Risk review: notional 29,605.00 USD against 250,000.00 USD buying power "
    "(11.8% utilization). Position concentration 6.2%, under the 10.0% single "
    "name cap. Result: PASS."
)
AUDIT_LINE = (
    "AUDIT 2026-03-11T09:31:07Z node=worker_c_validator ref=MOCK-8842 "
    "action=validate outcome=accepted checked_items=3"
)


class DeterministicSummarizer:
    """Records its calls so tests can assert no LLM work happens when idle."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    def summarize(self, messages: Sequence[MessageRecord]) -> str:
        self.calls.append(len(messages))
        return f"Compressed {len(messages)} earlier trading turns: NVDA thesis held."


def build_bloated_history() -> list[MessageRecord]:
    return [
        MessageRecord(role="system", content=SYSTEM_INSTRUCTION),
        MessageRecord(
            role="tool",
            kind="tool_output",
            content=STALE_ORDER_BOOK,
            obsolete=True,
        ),
        *[
            MessageRecord(
                role="user",
                content=(
                    f"Round {index}: NVDA 20-day SMA 118.42 above 50-day SMA "
                    f"114.87 on 2.3x volume, RSI(14) 61.8, MACD positive. "
                ) * 3,
            )
            for index in range(6)
        ],
        MessageRecord(role="assistant", kind="tool_output", content=ORDER_PAYLOAD),
        MessageRecord(role="tool", kind="tool_output", content=COMPLIANCE_CHECK),
        MessageRecord(role="user", content=AUDIT_LINE),
    ]


def build_small_history() -> list[MessageRecord]:
    return [
        MessageRecord(role="system", content=SYSTEM_INSTRUCTION),
        MessageRecord(role="user", content="Evaluate a 250 share NVDA long."),
    ]


def make_node(
    summarizer: DeterministicSummarizer,
    *,
    token_limit: int,
    retain_recent: int,
):
    return make_context_manager_node(
        token_counter=ApproximateTokenCounter(),
        summarizer=summarizer,
        token_limit=token_limit,
        retain_recent=retain_recent,
    )


def test_node_returns_only_the_three_context_keys() -> None:
    state = AgentState(raw_input="Evaluate NVDA", messages=build_bloated_history())
    node = make_node(DeterministicSummarizer(), token_limit=120, retain_recent=2)
    updates = node(state)
    assert set(updates) == {"messages", "context_summary", "context_metrics"}


def test_under_limit_passes_history_through_untouched() -> None:
    messages = build_small_history()
    state = AgentState(raw_input="Evaluate NVDA", messages=messages)
    summarizer = DeterministicSummarizer()
    node = make_node(summarizer, token_limit=5_000, retain_recent=2)

    updates = node(state)

    assert updates["messages"] == messages
    assert summarizer.calls == []
    metrics = updates["context_metrics"]
    assert isinstance(metrics, ContextMetrics)
    assert metrics.before_tokens == metrics.after_tokens
    assert metrics.pruned_messages == 0
    assert metrics.summarized_messages == 0


def test_under_limit_preserves_an_existing_summary() -> None:
    """The ``result.summary or state.context_summary`` fallback path."""
    earlier_summary = "Earlier rounds: NVDA thesis approved, compliance PASS."
    state = AgentState(
        raw_input="Evaluate NVDA",
        messages=build_small_history(),
        context_summary=earlier_summary,
    )
    node = make_node(DeterministicSummarizer(), token_limit=5_000, retain_recent=2)

    updates = node(state)

    assert updates["context_summary"] == earlier_summary


def test_under_limit_with_no_prior_summary_stays_none() -> None:
    state = AgentState(raw_input="Evaluate NVDA", messages=build_small_history())
    node = make_node(DeterministicSummarizer(), token_limit=5_000, retain_recent=2)

    updates = node(state)

    assert updates["context_summary"] is None


def test_over_limit_replaces_a_stale_summary_with_the_new_one() -> None:
    state = AgentState(
        raw_input="Evaluate NVDA",
        messages=build_bloated_history(),
        context_summary="Superseded summary from an earlier round.",
    )
    summarizer = DeterministicSummarizer()
    node = make_node(summarizer, token_limit=120, retain_recent=2)

    updates = node(state)

    assert summarizer.calls
    assert updates["context_summary"] != "Superseded summary from an earlier round."
    assert "Compressed" in str(updates["context_summary"])


def test_over_limit_prunes_obsolete_output_and_keeps_the_safety_rule() -> None:
    state = AgentState(raw_input="Evaluate NVDA", messages=build_bloated_history())
    node = make_node(DeterministicSummarizer(), token_limit=120, retain_recent=2)

    updates = node(state)
    messages = updates["messages"]

    assert any(message.role == "system" for message in messages)
    assert any(message.content == SYSTEM_INSTRUCTION for message in messages)
    assert all("Level-2 snapshot" not in message.content for message in messages)
    assert any(message.kind == "summary" for message in messages)

    metrics = updates["context_metrics"]
    assert metrics.after_tokens < metrics.before_tokens
    assert metrics.pruned_messages > 0
    assert metrics.summarized_messages > 0


def test_node_does_not_mutate_the_incoming_state() -> None:
    messages = build_bloated_history()
    snapshot = deepcopy(messages)
    state = AgentState(raw_input="Evaluate NVDA", messages=messages)
    node = make_node(DeterministicSummarizer(), token_limit=120, retain_recent=2)

    node(state)

    assert state.messages == snapshot
    assert messages == snapshot


def test_updates_are_assignable_back_onto_the_frozen_contract() -> None:
    """Guards the tuple-vs-list boundary: AgentState is strict about types."""
    state = AgentState(raw_input="Evaluate NVDA", messages=build_bloated_history())
    node = make_node(DeterministicSummarizer(), token_limit=120, retain_recent=2)

    updates = node(state)
    for field, value in updates.items():
        setattr(state, field, value)

    assert isinstance(state.messages, list)
    assert state.context_metrics.after_tokens <= 120
    assert any(message.role == "system" for message in state.messages)


def test_repeated_visits_converge_and_stay_bounded() -> None:
    """The node runs before every Coordinator visit, so it must be idempotent."""
    state = AgentState(raw_input="Evaluate NVDA", messages=build_bloated_history())
    node = make_node(DeterministicSummarizer(), token_limit=120, retain_recent=2)

    first = node(state)
    for field, value in first.items():
        setattr(state, field, value)
    second = node(state)

    assert second["context_metrics"].after_tokens <= 120
    assert second["context_metrics"].pruned_messages == 0
    assert second["messages"] == first["messages"]
    assert second["context_summary"] == first["context_summary"]
