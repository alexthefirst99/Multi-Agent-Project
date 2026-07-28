from __future__ import annotations

from app.services.backend_adapters import (
    run_live_loop_check,
    run_live_tool_check,
)


def test_live_loop_guard_uses_five_round_circuit_breaker() -> None:
    result = run_live_loop_check(inject_failure=True)
    assert result.triggered is True
    assert result.rounds == 5
    assert result.route == "worker_d_reporter"
    assert result.degraded is True


def test_live_loop_guard_nominal_check_does_not_trigger() -> None:
    result = run_live_loop_check(inject_failure=False)
    assert result.triggered is False
    assert result.rounds == 1
    assert result.route == "worker_a_analyzer"


def test_live_tool_guard_rejects_rogue_call_atomically() -> None:
    result = run_live_tool_check(inject_failure=True)
    assert result.triggered is True
    assert result.approved_count == 0
    assert result.executed_count == 0


def test_live_tool_guard_executes_only_mocked_safe_call() -> None:
    result = run_live_tool_check(inject_failure=False)
    assert result.triggered is False
    assert result.approved_count == 1
    assert result.executed_count == 1
