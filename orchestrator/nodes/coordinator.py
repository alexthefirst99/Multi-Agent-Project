"""Coordinator node and deterministic routing policy."""

from __future__ import annotations

from contract import (
    AgentState,
    GraphError,
    RouteAuditEntry,
    RouteName,
    TerminationReason,
)
from orchestrator.guardrails.loop_guard import increment_round
from orchestrator.routing import WORKER_A_ROUTE, WORKER_B_ROUTE, WORKER_D_ROUTE


def coordinator_node(state: AgentState) -> dict[str, object]:
    """Increment the round counter and select exactly one deterministic route."""
    decision = increment_round(state.round_number, max_rounds=state.max_rounds)
    route: RouteName
    reason: str
    degraded = False
    termination_reason: TerminationReason | None = None
    errors = list(state.errors)

    # Successful completion takes precedence over the circuit breaker because no
    # additional worker cycle will run after this route.
    if state.is_validated:
        route = WORKER_D_ROUTE
        reason = "Validation passed; produce the complete audit report."
        termination_reason = "completed"
    elif state.analysis_schema_error:
        route = WORKER_D_ROUTE
        reason = (
            "Analyzer failed its single correction retry; produce a partial report."
        )
        degraded = True
        termination_reason = "analysis_schema_error"
    elif decision.limit_reached:
        route = WORKER_D_ROUTE
        reason = "Five Coordinator visits reached; stop the non-converging loop."
        degraded = True
        termination_reason = "round_limit_reached"
        if not any(error.code == "round_limit_reached" for error in errors):
            errors.append(
                GraphError(
                    code="round_limit_reached",
                    message="The deterministic five-round circuit breaker activated.",
                    node="coordinator",
                    recoverable=False,
                )
            )
    elif state.rejection_flag or state.rollback_requested:
        route = WORKER_A_ROUTE
        reason = "Validator requested rollback; return to the Analyzer."
    elif state.analysis_payload is None:
        route = WORKER_A_ROUTE
        reason = "No structured analysis exists."
    else:
        route = WORKER_B_ROUTE
        reason = "Structured analysis is ready for guarded mock execution."

    history = list(state.routing_history)
    history.append(
        RouteAuditEntry(
            round_number=decision.round_number,
            next_route=route,
            reason=reason,
            degraded=degraded,
        )
    )
    return {
        "round_number": decision.round_number,
        "next_route": route,
        "route_reason": reason,
        "routing_history": history,
        "degraded_output": degraded,
        "termination_reason": termination_reason,
        "errors": errors,
    }


__all__ = ["coordinator_node"]
