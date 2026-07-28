"""Deterministic infinite-loop failure reproduction for Quynh."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from contract import AgentState, AnalysisPayload
from snippet import coordinator_node

SAMPLE_ROUNDS = 25
TOKENS_PER_ROUND = 1_200
WORKER_A_ROUTE = "worker_a_analyzer"
WORKER_D_ROUTE = "worker_d_reporter"


@dataclass(frozen=True, slots=True)
class DemoResult:
    rounds: int
    terminated: bool
    final_route: str
    degraded: bool
    round_limit_errors: int


def apply(state: AgentState, updates: dict[str, object]) -> AgentState:
    """Apply node updates through the canonical Pydantic contract."""
    data = state.model_dump(mode="python")
    data.update(updates)
    return AgentState.model_validate(data)


def adversarial_state() -> AgentState:
    """Return a stable rollback fixture that never converges on its own."""
    return AgentState(
        raw_input="Adversarial mock signal that never passes validation.",
        analysis_payload=AnalysisPayload(
            ticker="AAPL",
            side="buy",
            quantity=10,
            confidence=0.7,
            rationale="A deterministic fixture that forces repeated rollback.",
            risk_level="medium",
        ),
        rejection_flag=True,
        rollback_requested=True,
        rejection_reason="The mock validator always rejects this action.",
    )


def unsafe_coordinator_node(state: AgentState) -> dict[str, object]:
    """Intentionally unsafe fixture: route rollback upstream forever."""
    return {
        "round_number": state.round_number + 1,
        "next_route": WORKER_A_ROUTE,
        "route_reason": "Unsafe model-driven retry with no circuit breaker.",
    }


def run_without_guardrail() -> DemoResult:
    state = adversarial_state()
    for _ in range(SAMPLE_ROUNDS):
        state = apply(state, unsafe_coordinator_node(state))
    return DemoResult(
        rounds=state.round_number,
        terminated=False,
        final_route=state.next_route or WORKER_A_ROUTE,
        degraded=False,
        round_limit_errors=0,
    )


def run_with_guardrail() -> DemoResult:
    state = adversarial_state()
    while True:
        state = apply(state, coordinator_node(state))
        if state.next_route == WORKER_D_ROUTE:
            return DemoResult(
                rounds=state.round_number,
                terminated=True,
                final_route=state.next_route,
                degraded=state.degraded_output,
                round_limit_errors=sum(
                    error.code == "round_limit_reached" for error in state.errors
                ),
            )


def main() -> None:
    before = run_without_guardrail()
    after = run_with_guardrail()
    before_tokens = before.rounds * TOKENS_PER_ROUND
    after_tokens = after.rounds * TOKENS_PER_ROUND
    token_reduction = 100 * (before_tokens - after_tokens) / before_tokens

    print("=== WITHOUT GUARDRAIL ===")
    print(f"Observed rounds: {before.rounds} (safety sample still active)")
    print(f"Terminated: {before.terminated}")
    print(f"Final route: {before.final_route}")
    print(f"Estimated tokens: {before_tokens}")

    print("\n=== WITH GUARDRAIL ===")
    print(f"Observed rounds: {after.rounds}")
    print(f"Terminated: {after.terminated}")
    print(f"Final route: {after.final_route}")
    print(f"Degraded partial output: {after.degraded}")
    print(f"Round-limit errors recorded: {after.round_limit_errors}")
    print(f"Estimated tokens: {after_tokens}")

    print("\n=== METRICS ===")
    print(f"Observed round reduction: {before.rounds - after.rounds}")
    print(f"Estimated token reduction: {token_reduction:.1f}%")
    print("Deterministic termination rate: 0% -> 100%")

    assert before.terminated is False
    assert before.final_route == WORKER_A_ROUTE
    assert after.terminated is True
    assert after.rounds == 5
    assert after.final_route == WORKER_D_ROUTE
    assert after.degraded is True
    assert after.round_limit_errors == 1


if __name__ == "__main__":
    main()
