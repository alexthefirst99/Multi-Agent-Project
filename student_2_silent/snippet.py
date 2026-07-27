"""
Student 2 — Worker A (Analyzer)
Critical Failure Mode: Silent Hallucinations & Structural Failures

The Failure: Worker A receives unformatted data, outputs a confident text
answer that misses critical domain identifiers, causing silent processing
failures downstream.

The Guardrail: Force Worker A to use an explicit schema object via
.with_structured_output(ContractSchema). Catch raw LLM schema parsing
validation errors programmatically within an error handling wrapper, then
route the error exception text back to the node once for an automated
self-correcting retry.

TODO: implement the Analyzer node + its structured-output guardrail here.
"""

from contract import AgentState


def worker_a_analyzer_node(state: AgentState) -> AgentState:
    raise NotImplementedError("TODO: implement structured-output validation + one self-correcting retry.")
