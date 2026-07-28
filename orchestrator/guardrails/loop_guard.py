"""Deterministic round counting and circuit breaking."""

from __future__ import annotations

from dataclasses import dataclass

from contract import MAX_COORDINATOR_ROUNDS


class LoopGuardError(ValueError):
    """Raised when the round counter violates the frozen contract."""


@dataclass(frozen=True, slots=True)
class LoopGuardDecision:
    """Result of one Coordinator visit."""

    round_number: int
    limit_reached: bool


def increment_round(
    current_round: int,
    *,
    max_rounds: int = MAX_COORDINATOR_ROUNDS,
) -> LoopGuardDecision:
    """Increment the Coordinator counter and evaluate the five-round limit."""
    if isinstance(current_round, bool) or not isinstance(current_round, int):
        raise LoopGuardError("current_round must be an integer.")
    if current_round < 0:
        raise LoopGuardError("current_round cannot be negative.")
    if isinstance(max_rounds, bool) or not isinstance(max_rounds, int):
        raise LoopGuardError("max_rounds must be an integer.")
    if max_rounds != MAX_COORDINATOR_ROUNDS:
        raise LoopGuardError("The frozen contract fixes max_rounds at five.")

    next_round = current_round + 1
    return LoopGuardDecision(
        round_number=next_round,
        limit_reached=next_round >= max_rounds,
    )


__all__ = ["LoopGuardDecision", "LoopGuardError", "increment_round"]
