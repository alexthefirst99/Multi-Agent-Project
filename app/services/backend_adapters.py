"""Thin UI adapters for the two completed production guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contract import AgentState
from orchestrator.guardrails.tool_guard import (
    InvalidToolCallException,
    guard_and_execute_tool_batch,
)
from orchestrator.nodes.coordinator import coordinator_node
from orchestrator.tools.mock_tools import build_default_tool_registry


@dataclass(frozen=True, slots=True)
class LoopCheck:
    triggered: bool
    rounds: int
    route: str
    degraded: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ToolCheck:
    triggered: bool
    approved_count: int
    executed_count: int
    message: str


def run_live_loop_check(*, inject_failure: bool) -> LoopCheck:
    """Exercise the real Coordinator and loop guard with deterministic state."""
    state = AgentState(raw_input="UI guardrail demonstration")
    visits = 5 if inject_failure else 1
    updates: dict[str, Any] = {}
    for _ in range(visits):
        updates = coordinator_node(state)
        state = state.model_copy(update=updates)
        if state.termination_reason == "round_limit_reached":
            break

    return LoopCheck(
        triggered=state.termination_reason == "round_limit_reached",
        rounds=state.round_number,
        route=state.next_route or "worker_a_analyzer",
        degraded=state.degraded_output,
        reason=state.route_reason or "Coordinator route evaluated.",
    )


def run_live_tool_check(*, inject_failure: bool) -> ToolCheck:
    """Exercise Alex's real atomic tool guard against the mock registry."""
    registry = build_default_tool_registry()
    raw_calls: list[dict[str, object]]
    if inject_failure:
        raw_calls = [
            {
                "tool_name": "delete_production_database",
                "arguments": {"confirm": True},
            }
        ]
    else:
        raw_calls = [
            {
                "tool_name": "execute_trade",
                "arguments": {"ticker": "AAPL", "side": "buy", "quantity": 10},
            }
        ]

    try:
        result = guard_and_execute_tool_batch(raw_calls, registry)
    except InvalidToolCallException as exc:
        return ToolCheck(
            triggered=True,
            approved_count=0,
            executed_count=0,
            message=str(exc),
        )

    return ToolCheck(
        triggered=False,
        approved_count=len(result.approved_calls),
        executed_count=len(result.raw_results),
        message="Atomic validation passed; one mocked tool executed.",
    )
