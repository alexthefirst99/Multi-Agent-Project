"""Deterministic downstream-cascade failure reproduction. All actions are mocks.

WITHOUT the guardrail, raw Worker B output flows straight into Worker C's
business logic: a result missing its required keys raises ``KeyError`` and a
string quantity raises ``TypeError`` in notional arithmetic. WITH the
guardrail, ``validate_sanitize_node`` rejects both records before any
downstream code runs and the Coordinator re-routes to the Analyzer.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from snippet import validate_sanitize_node, validator_node

from contract import AgentState, AnalysisPayload
from orchestrator.nodes.coordinator import coordinator_node

MOCK_PRICE = 189.75

ANALYSIS = AnalysisPayload(
    ticker="AAPL",
    side="buy",
    quantity=10,
    confidence=0.8,
    rationale="Unusual volume supports a small mocked position.",
    risk_level="medium",
)

# Worker B mock output that lost its status and reference_id fields upstream.
MISSING_KEYS = {
    "tool_name": "execute_trade",
    "success": True,
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10,
}
# Worker B mock output whose quantity is prose instead of an integer.
TYPE_CONFUSED = {
    "tool_name": "execute_trade",
    "success": True,
    "status": "mock_success",
    "reference_id": "mock-1",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": "ten",
}
WELL_FORMED = {
    "tool_name": "execute_trade",
    "success": True,
    "status": "mock_success",
    "reference_id": "mock-1",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10,
}


def unsafe_worker_c(raw_results: list[dict[str, object]]) -> list[str]:
    """Worker C business logic with no sanitization node in place."""
    lines = []
    for raw in raw_results:
        notional = round(MOCK_PRICE * raw["quantity"], 2)  # type: ignore[operator]
        lines.append(
            f"{raw['tool_name']} -> {raw['status']} "
            f"(ref={raw['reference_id']}, notional=${notional})"
        )
    return lines


def crash_type(raw: dict[str, object]) -> str | None:
    try:
        unsafe_worker_c([raw])
    except (KeyError, TypeError) as exc:
        return type(exc).__name__
    return None


def guarded_outcome(raw: dict[str, object]) -> tuple[AgentState, str]:
    """Run the guarded Worker C node, then ask the Coordinator for the route."""
    state = AgentState(
        raw_input="AAPL rose 4% in ten minutes on unusual volume; consider 10 shares.",
        analysis_payload=ANALYSIS,
        pending_actor_output=[raw],
    )
    after_validator = state.model_copy(update=validator_node(state))
    routed = after_validator.model_copy(update=coordinator_node(after_validator))
    if routed.next_route is None:
        raise AssertionError("Coordinator did not choose a route.")
    return after_validator, routed.next_route


def main() -> None:
    unguarded_crashes = {
        "missing keys": crash_type(MISSING_KEYS),
        "string quantity": crash_type(TYPE_CONFUSED),
    }

    rejected_states = {
        label: guarded_outcome(raw)
        for label, raw in (
            ("missing keys", MISSING_KEYS),
            ("string quantity", TYPE_CONFUSED),
        )
    }
    clean_state, clean_route = guarded_outcome(WELL_FORMED)

    print("=== WITHOUT GUARDRAIL ===")
    for label, crash in unguarded_crashes.items():
        print(f"Downstream Worker C crash on {label}: {crash}")
    print("Malformed results reaching business logic: 2/2")

    print("\n=== WITH GUARDRAIL ===")
    for label, (state, route) in rejected_states.items():
        print(
            f"Rejected {label} before business logic: "
            f"rejection_flag={state.rejection_flag}, "
            f"rollback_requested={state.rollback_requested}, "
            f"promoted results={len(state.tool_execution_results)}, "
            f"Coordinator re-route -> {route}"
        )
    print(
        f"Well-formed result still validated: is_validated={clean_state.is_validated}, "
        f"quantity={clean_state.tool_execution_results[0].quantity}, "
        f"Coordinator route -> {clean_route}"
    )

    print("\n=== METRICS ===")
    print("Downstream KeyError/TypeError crashes: 2/2 -> 0/2")
    print("Malformed results promoted into authoritative state: 2/2 -> 0/2")
    print("Graceful rollbacks routed to the Analyzer: 0/2 -> 2/2")
    print("Typed malformed_actor_output audit errors per rejection: 0 -> 1")
    print("Well-formed results validated and routed to the Reporter: 1/1")

    assert unguarded_crashes == {"missing keys": "KeyError", "string quantity": "TypeError"}
    for state, route in rejected_states.values():
        assert state.rejection_flag is True
        assert state.rollback_requested is True
        assert state.tool_execution_results == []
        audit_errors = sum(
            1 for error in state.errors if error.code == "malformed_actor_output"
        )
        assert audit_errors == 1
        assert route == "worker_a_analyzer"
    assert validate_sanitize_node(AgentState(raw_input="no actor output yet")) == {}
    assert clean_state.is_validated is True
    assert clean_state.tool_execution_results[0].quantity == 10
    assert clean_route == "worker_d_reporter"


if __name__ == "__main__":
    main()
