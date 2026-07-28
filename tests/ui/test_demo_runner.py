from __future__ import annotations

from app.models import GuardrailStatus, NodeStatus
from app.services.demo_runner import run_demo


def test_multiple_failures_trigger_independent_visual_states() -> None:
    result = run_demo(
        "Buy 10 AAPL shares because volume increased rapidly.",
        ["Infinite Loop", "Rogue Tool Call", "Privacy Leak"],
    )
    assert result.node_statuses["Coordinator"] is NodeStatus.GUARDED
    assert result.node_statuses["Actor"] is NodeStatus.GUARDED
    assert result.node_statuses["Reporter"] is NodeStatus.GUARDED
    assert result.live_checks["loop_guard"]["triggered"] is True
    assert result.live_checks["tool_guard"]["triggered"] is True
    assert len(result.triggered_guardrails) == 3


def test_unselected_guardrails_remain_enabled() -> None:
    result = run_demo("Summarize these three research papers.", [])
    assert result.execution_status == "Completed"
    assert all(item.status is GuardrailStatus.ENABLED for item in result.guardrails)
    assert result.agent_state["degraded_output"] is False
