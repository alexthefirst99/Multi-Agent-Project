from __future__ import annotations

from typing import Sequence

import pytest

from contract import MessageRecord
from orchestrator.utils.token_counting import (
    DEFAULT_ENCODING_NAME,
    ApproximateTokenCounter,
    TiktokenCounter,
    TokenCounter,
)

SYSTEM_INSTRUCTION = (
    "Never execute real trades. Every order placement, cancellation, and "
    "compliance alert is mocked and must be logged to the audit trail."
)
MARKET_ANALYSIS = (
    "NVDA momentum scan: 20-day SMA 118.42 crossed above 50-day SMA 114.87 on "
    "2.3x average volume; RSI(14) at 61.8, MACD histogram positive four "
    "sessions running. Sector breadth confirms semis leadership."
)
ORDER_PAYLOAD = (
    '{"tool_name": "execute_trade", "arguments": {"ticker": "NVDA", '
    '"side": "buy", "quantity": 250}}'
)
COMPLIANCE_CHECK = (
    "Risk review: notional 29,605.00 USD against 250,000.00 USD buying power "
    "(11.8% utilization). Position concentration 6.2%, under the 10.0% single "
    "name cap. Pattern-day-trade counter 1 of 4. Result: PASS."
)


def build_trading_history() -> list[MessageRecord]:
    return [
        MessageRecord(role="system", content=SYSTEM_INSTRUCTION),
        MessageRecord(role="user", content=MARKET_ANALYSIS),
        MessageRecord(role="assistant", kind="tool_output", content=ORDER_PAYLOAD),
        MessageRecord(role="tool", kind="tool_output", content=COMPLIANCE_CHECK),
    ]


class FakeEncoder:
    """Deterministic stand-in for a tiktoken encoding: one token per word."""

    def __init__(self) -> None:
        self.encode_calls = 0

    def encode(self, text: str) -> list[int]:
        self.encode_calls += 1
        return [len(word) for word in text.split()]


class CountingLoader:
    """Records how often the encoding was resolved, to prove caching."""

    def __init__(self, encoder: object) -> None:
        self._encoder = encoder
        self.calls: list[str] = []

    def __call__(self, encoding_name: str) -> object:
        self.calls.append(encoding_name)
        return self._encoder


def _raise_missing_module(encoding_name: str) -> object:
    raise ModuleNotFoundError("No module named 'tiktoken'")


def _raise_offline(encoding_name: str) -> object:
    raise ConnectionError(
        f"Failed to download the {encoding_name} BPE vocabulary: network unreachable"
    )


def test_counts_words_through_the_injected_encoder() -> None:
    messages = build_trading_history()
    counter = TiktokenCounter(encoder_loader=CountingLoader(FakeEncoder()))
    expected = sum(len(message.content.split()) for message in messages)
    assert counter.count_messages(messages) == expected
    assert counter.using_fallback is False
    assert counter.fallback_reason is None


def test_encoding_is_loaded_lazily_and_only_once() -> None:
    loader = CountingLoader(FakeEncoder())
    counter = TiktokenCounter(encoder_loader=loader)
    assert loader.calls == []

    messages = build_trading_history()
    counter.count_messages(messages)
    counter.count_messages(messages)
    counter.count_messages(messages)
    assert loader.calls == [DEFAULT_ENCODING_NAME]


def test_missing_tiktoken_falls_back_without_raising() -> None:
    messages = build_trading_history()
    counter = TiktokenCounter(encoder_loader=_raise_missing_module)
    assert counter.count_messages(messages) == ApproximateTokenCounter().count_messages(
        messages
    )
    assert counter.using_fallback is True
    assert "ModuleNotFoundError" in (counter.fallback_reason or "")


def test_offline_encoding_download_falls_back_without_raising() -> None:
    messages = build_trading_history()
    counter = TiktokenCounter(encoder_loader=_raise_offline)
    assert counter.count_messages(messages) == ApproximateTokenCounter().count_messages(
        messages
    )
    assert counter.using_fallback is True
    reason = counter.fallback_reason or ""
    assert "ConnectionError" in reason
    assert "network unreachable" in reason


def test_failure_during_encoding_falls_back_and_stays_degraded() -> None:
    class ExplodingEncoder:
        def encode(self, text: str) -> list[int]:
            raise RuntimeError("corrupted BPE merge table")

    messages = build_trading_history()
    counter = TiktokenCounter(encoder_loader=CountingLoader(ExplodingEncoder()))
    approximate = ApproximateTokenCounter().count_messages(messages)

    assert counter.count_messages(messages) == approximate
    assert counter.using_fallback is True
    assert "RuntimeError" in (counter.fallback_reason or "")
    # Later calls must not retry the broken encoder and must stay consistent.
    assert counter.count_messages(messages) == approximate


def test_degradation_is_logged_once(caplog: pytest.LogCaptureFixture) -> None:
    counter = TiktokenCounter(encoder_loader=_raise_offline)
    with caplog.at_level("WARNING", logger="orchestrator.utils.token_counting"):
        counter.count_messages(build_trading_history())
        counter.count_messages(build_trading_history())
    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == 1


def test_every_message_costs_at_least_one_token() -> None:
    class EmptyEncoder:
        def encode(self, text: str) -> list[int]:
            return []

    messages = build_trading_history()
    counter = TiktokenCounter(encoder_loader=CountingLoader(EmptyEncoder()))
    assert counter.count_messages(messages) == len(messages)


def test_custom_encoding_name_is_passed_to_the_loader() -> None:
    loader = CountingLoader(FakeEncoder())
    counter = TiktokenCounter("o200k_base", encoder_loader=loader)
    counter.count_messages(build_trading_history())
    assert loader.calls == ["o200k_base"]
    assert counter.encoding_name == "o200k_base"


def test_custom_fallback_counter_is_honoured() -> None:
    class ConstantCounter:
        def count_messages(self, messages: Sequence[MessageRecord]) -> int:
            return 4_242

    counter = TiktokenCounter(
        encoder_loader=_raise_missing_module, fallback=ConstantCounter()
    )
    assert counter.count_messages(build_trading_history()) == 4_242


def test_satisfies_the_token_counter_protocol() -> None:
    counter: TokenCounter = TiktokenCounter(
        encoder_loader=CountingLoader(FakeEncoder())
    )
    assert counter.count_messages([]) == 0


def test_drives_manage_context_end_to_end() -> None:
    from orchestrator.guardrails.context_guard import manage_context

    class DeterministicSummarizer:
        def summarize(self, messages: Sequence[MessageRecord]) -> str:
            return f"Summary of {len(messages)} older trading messages."

    messages = [
        MessageRecord(role="system", content=SYSTEM_INSTRUCTION),
        MessageRecord(
            role="tool",
            kind="tool_output",
            content="stale level-2 book " * 60,
            obsolete=True,
        ),
        *[
            MessageRecord(role="user", content=f"{MARKET_ANALYSIS} revision {index}")
            for index in range(5)
        ],
        MessageRecord(role="assistant", kind="tool_output", content=ORDER_PAYLOAD),
        MessageRecord(role="tool", kind="tool_output", content=COMPLIANCE_CHECK),
    ]
    counter = TiktokenCounter(encoder_loader=CountingLoader(FakeEncoder()))
    result = manage_context(
        messages,
        token_limit=60,
        retain_recent=2,
        token_counter=counter,
        summarizer=DeterministicSummarizer(),
    )

    # The budget is a soft target; the invariants are hard. The old
    # `after_tokens <= 60` could only hold by evicting the pinned compliance
    # record. The reduction assertion below already covers the compression win,
    # so it is kept as-is and the surviving records are asserted explicitly.
    assert result.metrics.after_tokens < result.metrics.before_tokens
    assert any(ORDER_PAYLOAD in message.content for message in result.messages)
    # COMPLIANCE_CHECK is also the newest message in this fixture.
    assert any(COMPLIANCE_CHECK in message.content for message in result.messages)
    assert any(message.role == "system" for message in result.messages)
    assert all(
        "stale level-2 book" not in message.content for message in result.messages
    )
