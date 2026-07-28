"""Central routing constants and LangGraph conditional-edge function."""

from __future__ import annotations

from contract import AgentState, RouteName

WORKER_A_ROUTE: RouteName = "worker_a_analyzer"
WORKER_B_ROUTE: RouteName = "worker_b_actor"
WORKER_D_ROUTE: RouteName = "worker_d_reporter"


def route_from_coordinator(state: AgentState) -> RouteName:
    if state.next_route is None:
        raise RuntimeError("Coordinator did not set next_route.")
    return state.next_route
