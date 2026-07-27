"""
Student 1 — Coordinator (Orchestrator)
Critical Failure Mode: Infinite Graph Loops

The Failure: The Coordinator node continuously re-routes tasks back to an
upstream node because the LLM fails to reach a terminating condition,
threatening to drain budget API tokens.

The Guardrail: Implement a strict, deterministic state["round_number"]
tracker directly into the LangGraph routing logic. If round_number >= 5,
short-circuit the graph flow, gracefully degrade, and route straight to a
final partial state output node.

TODO: implement the Coordinator node + its routing guardrail here.
"""

from contract import AgentState


def coordinator_node(state: AgentState) -> AgentState:
    raise NotImplementedError("TODO: implement the Coordinator node and its round_number guardrail.")
