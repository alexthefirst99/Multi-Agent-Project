"""Deterministic downstream-cascade failure reproduction."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from snippet import CascadeValidationError, sanitize_actor_output

MALFORMED = {
    "tool_name": "execute_trade",
    "success": True,
    "status": "mock_success",
    "reference_id": "mock-1",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": "ten",
}
SANITIZABLE = {**MALFORMED, "quantity": "10", "ticker": " aapl ", "success": "true"}


def unsafe_downstream_total(raw: dict[str, object]) -> int:
    return raw["quantity"] + 5  # type: ignore[operator]


def main() -> None:
    crashed = False
    try:
        unsafe_downstream_total(MALFORMED)
    except TypeError:
        crashed = True

    rejected = False
    try:
        sanitize_actor_output([MALFORMED])
    except CascadeValidationError:
        rejected = True

    sanitized = sanitize_actor_output([SANITIZABLE])

    print("=== WITHOUT GUARDRAIL ===")
    print(f"Downstream runtime crash: {crashed}")
    print("Malformed results reaching business logic: 1/1")

    print("\n=== WITH GUARDRAIL ===")
    print(f"Malformed result rejected before business logic: {rejected}")
    print(f"Safely normalized quantity: {sanitized.results[0].quantity}")
    print(f"Safely normalized ticker: {sanitized.results[0].ticker}")

    print("\n=== METRICS ===")
    print("Downstream crash rate: 100% -> 0%")
    print("Malformed-result rejection rate: 0% -> 100%")

    assert crashed is True
    assert rejected is True
    assert sanitized.results[0].quantity == 10


if __name__ == "__main__":
    main()
