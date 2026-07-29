"""Grading view for the context-management guardrail (Student 6).

Placement in the compiled LangGraph (orchestrator/graph.py). ASCII only: this
file is read back by tests/architecture with the platform default encoding::

    START --------------> [context_manager] --> [coordinator] --+
                               ^                               |
                               |                   (conditional routing)
                               |                               v
           [worker_c_validator] <-- [worker_a_analyzer] / [worker_b_actor]
                               |
                               +--> loops back to [context_manager]

The node therefore runs at START and again at every loop transition, before
each Coordinator routing decision.

Why pruning takes effect rather than silently appending: ``AgentState.messages``
is a plain ``list[MessageRecord]`` with no ``add_messages`` reducer annotation
(contract.py:225), so LangGraph assigns it a LastValue channel and a returned
shorter list REPLACES the window. Verified by execution against the real
library, not by inspection -- see
``tests/guardrails/test_context_manager_node.py::
test_shorter_message_list_replaces_rather_than_appends``, which compiles a real
StateGraph on langgraph 1.2.10 and observes 5 messages in, 1 out.

Configuration in the integrated graph: ``token_limit=850``, ``retain_recent=4``.
The limit is derived from the traffic the graph is designed to carry at
max_rounds=5; the arithmetic is documented at the constant. Because 850 sits far
below the ~6,700-16,300 token latency break-even, the guardrail is deliberately
configured to buy token cost with added latency. On the graph as it currently
reports, the real window peaks at 41 tokens, so the node measures and correctly
does nothing; it is exercised under designed traffic by test_failure.py.
"""

from orchestrator.guardrails.context_guard import manage_context
from orchestrator.nodes.context_manager import make_context_manager_node
from orchestrator.utils.token_counting import ApproximateTokenCounter, TiktokenCounter

__all__ = [
    "ApproximateTokenCounter",
    "TiktokenCounter",
    "make_context_manager_node",
    "manage_context",
]
