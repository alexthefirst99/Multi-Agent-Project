"""Worker B: guarded mapping from analysis to mocked tools."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pydantic import JsonValue

from contract import AgentState, GraphError
from orchestrator.guardrails.tool_guard import (
    InvalidToolCallException,
    guard_and_execute_tool_batch,
)
from orchestrator.tools.registry import ToolPermission, ToolRegistry

NodeCallable = Callable[[AgentState], dict[str, object]]


def _default_tool_calls(state: AgentState) -> list[JsonValue]:
    if state.analysis_payload is None:
        return []
    analysis = state.analysis_payload
    return [
        {
            "tool_name": "execute_trade",
            "arguments": {
                "ticker": analysis.ticker,
                "side": analysis.side,
                "quantity": analysis.quantity,
            },
        }
    ]


def make_actor_node(
    registry: ToolRegistry,
    *,
    permissions: Sequence[ToolPermission] | None = None,
) -> NodeCallable:
    def actor_node(state: AgentState) -> dict[str, object]:
        errors = list(state.errors)
        raw_calls = state.pending_tool_calls or _default_tool_calls(state)
        try:
            batch = guard_and_execute_tool_batch(
                raw_calls,
                registry,
                permissions=permissions,
            )
        except InvalidToolCallException as exc:
            errors.append(
                GraphError(
                    code="unauthorized_tool_call",
                    message=str(exc),
                    node="worker_b_actor",
                    recoverable=True,
                )
            )
            return {
                "approved_tool_calls": [],
                "pending_actor_output": [],
                # A rejected batch is a terminal Actor boundary. Clear every
                # downstream artifact so stale data from an earlier graph
                # cycle cannot be mistaken for this rejected attempt.
                "tool_execution_results": [],
                "validation_result": None,
                "is_validated": False,
                "rejection_flag": True,
                "rejection_reason": str(exc),
                "rollback_requested": True,
                "termination_reason": "tool_guard_rejection",
                "errors": errors,
            }

        return {
            "approved_tool_calls": list(batch.approved_calls),
            "pending_actor_output": [dict(result) for result in batch.raw_results],
            "rejection_flag": False,
            "rejection_reason": None,
            "rollback_requested": False,
            "errors": errors,
        }

    return actor_node
