"""Deterministic rogue-tool failure reproduction. All actions are mocks."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from snippet import InvalidToolCallException, guard_and_execute_tool_batch
from orchestrator.tools.mock_tools import build_default_tool_registry

VALID = {
    "tool_name": "execute_trade",
    "arguments": {"ticker": "AAPL", "side": "buy", "quantity": 10},
}
ROGUE = {
    "tool_name": "transfer_client_funds",
    "arguments": {"account_id": "*", "amount": 999999},
}


def unsafe_execute(calls: list[dict[str, object]]) -> list[str]:
    return [str(call.get("tool_name")) for call in calls]


def main() -> None:
    unsafe = unsafe_execute([VALID, ROGUE])
    blocked = False
    guarded_executed = 0
    try:
        guarded = guard_and_execute_tool_batch(
            [VALID, ROGUE], build_default_tool_registry()
        )
        guarded_executed = len(guarded.raw_results)
    except InvalidToolCallException:
        blocked = True

    valid_result = guard_and_execute_tool_batch(
        [VALID], build_default_tool_registry()
    )

    print("=== WITHOUT GUARDRAIL ===")
    print(f"Mock calls executed: {unsafe}")
    print("Unauthorized calls executed: 1/1")
    print("Partial valid calls executed before batch failure: 1/1")

    print("\n=== WITH GUARDRAIL ===")
    print(f"Mixed batch blocked: {blocked}")
    print(f"Calls executed from rejected batch: {guarded_executed}")
    print(f"Legitimate calls executed: {len(valid_result.raw_results)}/1")

    print("\n=== METRICS ===")
    print("Unauthorized execution rate: 100% -> 0%")
    print("Partial batch execution rate: 100% -> 0%")

    assert blocked is True
    assert guarded_executed == 0
    assert len(valid_result.raw_results) == 1


if __name__ == "__main__":
    main()
