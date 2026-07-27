"""
Student 4 — Worker C (Validator)
Critical Failure Mode: Downstream Cascade Failure

The Failure: Worker B passes malformed, unvalidated output data across the
state directly into Worker C, causing runtime application crashes or
arithmetic type errors in downstream code.

The Guardrail: Create an explicit Validation/Sanitization Node between
Worker B and Worker C. This node must parse the incoming state variable
using programmatic assertions. If the structural invariants fail, it
updates the state with a rejection flag and forces a rollback/routing
routine.

TODO: implement the Validator node + its sanitization guardrail here.
"""

from contract import AgentState


def validate_sanitize_node(state: AgentState) -> AgentState:
    raise NotImplementedError("TODO: assert structural invariants on Worker B's output; reject + roll back on violation.")


def worker_c_validator_node(state: AgentState) -> AgentState:
    raise NotImplementedError("TODO: evaluate system actions against initial analysis before final reporting.")
