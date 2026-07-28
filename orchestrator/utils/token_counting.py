"""Dependency-injectable token counting helpers."""

from __future__ import annotations

from math import ceil
from typing import Protocol, Sequence

from contract import MessageRecord


class TokenCounter(Protocol):
    def count_messages(self, messages: Sequence[MessageRecord]) -> int: ...


class ApproximateTokenCounter:
    """Deterministic four-characters-per-token estimate for offline tests."""

    def count_messages(self, messages: Sequence[MessageRecord]) -> int:
        return sum(max(1, ceil(len(message.content) / 4)) for message in messages)


class LangChainTokenCounter:
    """Adapter around a LangChain chat model's token counting method."""

    def __init__(self, model: object) -> None:
        self._model = model

    def count_messages(self, messages: Sequence[MessageRecord]) -> int:
        get_num_tokens = getattr(self._model, "get_num_tokens", None)
        if not callable(get_num_tokens):
            raise TypeError("The injected model does not expose get_num_tokens().")
        return sum(int(get_num_tokens(message.content)) for message in messages)
