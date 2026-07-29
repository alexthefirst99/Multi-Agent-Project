"""Dependency-injectable token counting helpers."""

from __future__ import annotations

import logging
from functools import lru_cache
from math import ceil
from typing import Protocol, Sequence

from contract import MessageRecord

DEFAULT_ENCODING_NAME = "cl100k_base"

_LOGGER = logging.getLogger(__name__)


class TokenCounter(Protocol):
    def count_messages(self, messages: Sequence[MessageRecord]) -> int: ...


class TextEncoder(Protocol):
    """The single tiktoken method this module depends on."""

    def encode(self, text: str) -> Sequence[int]: ...


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


@lru_cache(maxsize=8)
def _load_encoding(encoding_name: str) -> TextEncoder:
    """Import tiktoken and resolve an encoding, cached per encoding name.

    Imported lazily so the dependency is only touched when real counting is
    requested, and so an offline environment fails at call time rather than at
    module import time.
    """
    import tiktoken

    return tiktoken.get_encoding(encoding_name)


class TiktokenCounter:
    """Real BPE token counts that degrade to the approximate counter.

    Token measurement is a guardrail input, never the guardrail itself: a
    missing dependency or an unreachable encoding download must not stop the
    context manager from bounding history. Every failure path therefore falls
    back to ``ApproximateTokenCounter`` and records why, and ``count_messages``
    never raises.
    """

    def __init__(
        self,
        encoding_name: str = DEFAULT_ENCODING_NAME,
        *,
        encoder_loader: object | None = None,
        fallback: TokenCounter | None = None,
    ) -> None:
        self._encoding_name = encoding_name
        self._encoder_loader = (
            _load_encoding if encoder_loader is None else encoder_loader
        )
        self._fallback = ApproximateTokenCounter() if fallback is None else fallback
        self._encoder: TextEncoder | None = None
        self._load_attempted = False
        self._fallback_reason: str | None = None

    @property
    def encoding_name(self) -> str:
        return self._encoding_name

    @property
    def using_fallback(self) -> bool:
        """Whether counts are estimates. Resolves the encoding on first access."""
        return self._resolve_encoder() is None

    @property
    def fallback_reason(self) -> str | None:
        """Human-readable cause of degradation, or ``None`` when counts are exact."""
        self._resolve_encoder()
        return self._fallback_reason

    def _degrade(self, reason: str) -> None:
        self._encoder = None
        if self._fallback_reason != reason:
            self._fallback_reason = reason
            _LOGGER.warning(
                "TiktokenCounter is using approximate counts instead of %r: %s",
                self._encoding_name,
                reason,
            )

    def _resolve_encoder(self) -> TextEncoder | None:
        if self._load_attempted:
            return self._encoder
        self._load_attempted = True
        try:
            self._encoder = self._encoder_loader(self._encoding_name)
        except Exception as error:
            self._degrade(f"{type(error).__name__}: {error}")
        return self._encoder

    def count_messages(self, messages: Sequence[MessageRecord]) -> int:
        encoder = self._resolve_encoder()
        if encoder is None:
            return self._fallback.count_messages(messages)
        try:
            return sum(
                max(1, len(encoder.encode(message.content))) for message in messages
            )
        except Exception as error:
            # A mid-count failure degrades permanently so one run reports on
            # one consistent basis rather than mixing exact and estimated totals.
            self._degrade(f"{type(error).__name__}: {error}")
            return self._fallback.count_messages(messages)
