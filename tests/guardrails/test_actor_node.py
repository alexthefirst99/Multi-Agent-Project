from __future__ import annotations

from contract import AgentState, ToolExecutionResult, ValidationResult
from orchestrator.nodes.actor import make_actor_node
from orchestrator.tools.mock_tools import build_default_tool_registry

STALE_RESULT = ToolExecutionResult(
    tool_name="execute_trade",
    success=True,
    status="mock_success",
    reference_id="MOCK-TRADE-STALE-1",
)


def test_rejection_clears_stale_downstream_fields() -> None:
    """A rejected batch is a terminal Actor boundary: stale data left over from an
    earlier graph cycle (e.g. a previous round's execution result or validation)
    must not survive into this rejected attempt, mirroring the equivalent fix in
    ``orchestrator/nodes/analyzer.py``.
    """
    actor = make_actor_node(build_default_tool_registry())
    stale_state = {
        "pending_tool_calls": [{"tool_name": "forbidden_tool", "arguments": {}}],
        "tool_execution_results": [STALE_RESULT],
        "validation_result": ValidationResult(accepted=True, reason="stale approval"),
        "is_validated": True,
    }

    state = AgentState(raw_input="test", **stale_state)
    updates = actor(state)

    assert updates["rejection_flag"] is True
    assert updates["rollback_requested"] is True
    assert updates["tool_execution_results"] == []
    assert updates["validation_result"] is None
    assert updates["is_validated"] is False
    assert updates["approved_tool_calls"] == []
    assert updates["pending_actor_output"] == []
