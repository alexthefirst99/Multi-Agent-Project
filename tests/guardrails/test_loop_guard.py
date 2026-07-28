from __future__ import annotations

from copy import deepcopy

import pytest

from contract import AgentState, AnalysisPayload
from orchestrator.guardrails.loop_guard import LoopGuardError, increment_round
from orchestrator.nodes.coordinator import coordinator_node
from orchestrator.routing import WORKER_A_ROUTE, WORKER_B_ROUTE, WORKER_D_ROUTE

VALID_ANALYSIS = AnalysisPayload(
    ticker="AAPL",
    side="buy",
    quantity=10,
    confidence=0.7,
    rationale="A deterministic adversarial fixture for loop testing.",
    risk_level="medium",
)


def apply(state: AgentState, updates: dict[str, object]) -> AgentState:
    data = state.model_dump(mode="python")
    data.update(updates)
    return AgentState.model_validate(data)


def test_boundary_is_exactly_five_rounds() -> None:
    assert increment_round(3).limit_reached is False
    decision = increment_round(4)
    assert decision.round_number == 5
    assert decision.limit_reached is True


@pytest.mark.parametrize("value", [-1, True, 1.5, "1", None])
def test_malformed_round_counter_is_rejected(value: object) -> None:
    with pytest.raises(LoopGuardError):
        increment_round(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, 4, 6, True, 5.0])
def test_frozen_round_limit_cannot_be_overridden(value: object) -> None:
    with pytest.raises(LoopGuardError):
        increment_round(0, max_rounds=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("state", "expected_route", "expected_termination", "expected_degraded"),
    [
        (
            AgentState(raw_input="missing analysis"),
            WORKER_A_ROUTE,
            None,
            False,
        ),
        (
            AgentState(raw_input="analysis ready", analysis_payload=VALID_ANALYSIS),
            WORKER_B_ROUTE,
            None,
            False,
        ),
        (
            AgentState(raw_input="validated", is_validated=True),
            WORKER_D_ROUTE,
            "completed",
            False,
        ),
        (
            AgentState(raw_input="schema failed", analysis_schema_error=True),
            WORKER_D_ROUTE,
            "analysis_schema_error",
            True,
        ),
        (
            AgentState(
                raw_input="rollback",
                analysis_payload=VALID_ANALYSIS,
                rejection_flag=True,
                rollback_requested=True,
            ),
            WORKER_A_ROUTE,
            None,
            False,
        ),
    ],
)
def test_routing_policy_is_deterministic(
    state: AgentState,
    expected_route: str,
    expected_termination: str | None,
    expected_degraded: bool,
) -> None:
    updated = apply(state, coordinator_node(state))
    assert updated.next_route == expected_route
    assert updated.termination_reason == expected_termination
    assert updated.degraded_output is expected_degraded
    assert updated.round_number == 1
    assert updated.routing_history[-1].next_route == expected_route


def test_non_converging_state_routes_to_degraded_report_at_round_five() -> None:
    state = AgentState(
        raw_input="adversarial signal",
        analysis_payload=VALID_ANALYSIS,
        rejection_flag=True,
        rollback_requested=True,
    )

    for expected_round in range(1, 6):
        state = apply(state, coordinator_node(state))
        assert state.round_number == expected_round
        if expected_round < 5:
            assert state.next_route == WORKER_A_ROUTE

    assert state.next_route == WORKER_D_ROUTE
    assert state.degraded_output is True
    assert state.termination_reason == "round_limit_reached"
    assert len(state.routing_history) == 5
    assert state.routing_history[-1].degraded is True
    assert [error.code for error in state.errors].count("round_limit_reached") == 1


def test_coordinator_does_not_mutate_authoritative_input_state() -> None:
    state = AgentState(
        raw_input="adversarial signal",
        round_number=4,
        analysis_payload=VALID_ANALYSIS,
        rejection_flag=True,
        rollback_requested=True,
    )
    original = deepcopy(state)

    updates = coordinator_node(state)

    assert state == original
    assert state.round_number == 4
    assert state.routing_history == []
    assert updates["round_number"] == 5
    assert updates["next_route"] == WORKER_D_ROUTE


def test_repeated_terminal_evaluation_does_not_duplicate_round_limit_error() -> None:
    state = AgentState(
        raw_input="adversarial signal",
        round_number=4,
        analysis_payload=VALID_ANALYSIS,
        rejection_flag=True,
        rollback_requested=True,
    )
    terminal = apply(state, coordinator_node(state))
    repeated = apply(terminal, coordinator_node(terminal))

    assert repeated.next_route == WORKER_D_ROUTE
    assert [error.code for error in repeated.errors].count("round_limit_reached") == 1


@pytest.mark.parametrize(
    ("state", "termination_reason"),
    [
        (
            AgentState(
                raw_input="validated at boundary",
                round_number=4,
                is_validated=True,
            ),
            "completed",
        ),
        (
            AgentState(
                raw_input="schema failure at boundary",
                round_number=4,
                analysis_schema_error=True,
            ),
            "analysis_schema_error",
        ),
    ],
)
def test_existing_terminal_state_takes_precedence_over_round_limit(
    state: AgentState,
    termination_reason: str,
) -> None:
    updated = apply(state, coordinator_node(state))

    assert updated.round_number == 5
    assert updated.next_route == WORKER_D_ROUTE
    assert updated.termination_reason == termination_reason
    assert not any(error.code == "round_limit_reached" for error in updated.errors)
