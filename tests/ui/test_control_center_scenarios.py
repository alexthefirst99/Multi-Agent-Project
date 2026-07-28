from __future__ import annotations

import pytest

from app.mock_data import (
    DEFAULT_INJECTED_FAILURES,
    EXAMPLE_PROMPTS,
    FAILURES,
    SCENARIO_GUARDRAIL,
    SCENARIOS,
)
from app.models import TimelineStatus
from app.services.demo_runner import run_demo
from app.state import (
    initialize_state,
    reset_dashboard,
    selected_failures,
    selected_guardrails,
    failure_tick_key,
    guardrail_key,
    sync_failure_ticks,
    sync_guardrail_ticks,
    sync_injected_guardrails,
    sync_scenario_defaults,
)


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("mode", ("WITHOUT Guardrail", "WITH Guardrail"))
def test_every_scenario_supports_both_execution_modes(
    scenario: str,
    mode: str,
) -> None:
    failures = (
        DEFAULT_INJECTED_FAILURES
        if scenario == "Multiple Failures"
        else ()
        if scenario == "Happy Path"
        else (scenario,)
    )
    guardrails = tuple(SCENARIO_GUARDRAIL[item] for item in failures)
    result = run_demo(
        "Buy 10 AAPL shares because volume increased rapidly.",
        failures,
        scenario=scenario,
        execution_mode=mode,
        selected_guardrails=guardrails,
    )
    assert result.timeline
    assert result.execution_mode == mode
    assert [event.sequence for event in result.timeline] == list(
        range(1, len(result.timeline) + 1)
    )


def test_infinite_loop_timeline_visibly_repeats_rounds_and_forces_route() -> None:
    without = run_demo(
        "Loop demonstration",
        ["Infinite Loop"],
        scenario="Infinite Loop",
        execution_mode="WITHOUT Guardrail",
        selected_guardrails=["Infinite Loop Guardrail"],
    )
    with_guard = run_demo(
        "Loop demonstration",
        ["Infinite Loop"],
        scenario="Infinite Loop",
        execution_mode="WITH Guardrail",
        selected_guardrails=["Infinite Loop Guardrail"],
    )
    assert sum("started round" in event.title for event in without.timeline) >= 5
    assert without.timeline[-1].status is TimelineStatus.STILL_RUNNING
    assert without.timeline[-1].title == "Still Running"
    assert "was not terminated" in without.timeline[-1].detail
    assert any("Guardrail triggered" in event.title for event in with_guard.timeline)
    assert any("Forced route to Reporter" in event.title for event in with_guard.timeline)


def test_rollback_timeline_returns_to_coordinator_and_retries() -> None:
    result = run_demo(
        "Rollback demonstration",
        ["Cascade Failure"],
        scenario="Cascade Failure",
        execution_mode="WITH Guardrail",
        selected_guardrails=["Rollback Guardrail"],
    )
    timeline_text = " ".join(
        f"{event.source} {event.title} {event.detail}" for event in result.timeline
    )
    assert "Rollback" in timeline_text
    assert "Coordinator" in timeline_text
    assert "Retry" in timeline_text
    assert result.summary.rollback_count == 1


def test_state_helpers_sync_scenario_and_guardrails() -> None:
    state: dict[str, object] = {}
    initialize_state(state)
    state["selected_scenario"] = "Multiple Failures"
    sync_scenario_defaults(state)
    assert tuple(state["injected_failures"]) == DEFAULT_INJECTED_FAILURES
    assert selected_failures(state) == DEFAULT_INJECTED_FAILURES

    state["injected_failures"] = ["Privacy Leak", "Context Explosion"]
    sync_injected_guardrails(state)
    assert selected_guardrails(state) == ()

    state["result"] = object()
    state["timeline_events"] = (object(),)
    state["execution_summary"] = object()
    state["active_tab_data"] = {"metrics": object()}
    state["run_status"] = "Completed"
    reset_dashboard(state)
    assert state["result"] is None
    assert state["timeline_events"] == ()
    assert state["execution_summary"] is None
    assert state["active_tab_data"] == {}
    assert state["selected_scenario"] == "Happy Path"
    assert state["execution_mode"] == "WITHOUT Guardrail"


def test_prompt_suggestions_are_financial_trading_tasks() -> None:
    financial_terms = {
        "aapl",
        "shares",
        "order",
        "trade",
        "msft",
        "nvda",
        "tsla",
        "position",
    }
    for prompt in EXAMPLE_PROMPTS:
        normalized = prompt.lower()
        assert any(term in normalized for term in financial_terms)


def test_failure_ticks_infer_individual_multiple_and_happy_path() -> None:
    state: dict[str, object] = {}
    initialize_state(state)
    assert selected_failures(state) == ()
    assert state["selected_scenario"] == "Happy Path"

    state[failure_tick_key("Infinite Loop")] = True
    state[failure_tick_key("Rogue Tool Call")] = True
    sync_failure_ticks(state)
    assert state["selected_scenario"] == "Multiple Failures"
    assert selected_failures(state) == ("Infinite Loop", "Rogue Tool Call")
    assert selected_guardrails(state) == ()

    for failure in FAILURES:
        state[failure_tick_key(failure)] = False
    sync_failure_ticks(state)
    assert state["selected_scenario"] == "Happy Path"


def test_guardrail_ticks_derive_execution_mode() -> None:
    state: dict[str, object] = {}
    initialize_state(state)
    assert state["execution_mode"] == "WITHOUT Guardrail"

    state[guardrail_key("Privacy Guardrail")] = True
    sync_guardrail_ticks(state)
    assert state["execution_mode"] == "WITH Guardrail"

    state[guardrail_key("Privacy Guardrail")] = False
    sync_guardrail_ticks(state)
    assert state["execution_mode"] == "WITHOUT Guardrail"


def test_happy_path_ends_completed_not_safe_exit() -> None:
    result = run_demo(
        "Buy 10 AAPL shares because volume increased rapidly.",
        [],
        scenario="Happy Path",
        execution_mode="WITHOUT Guardrail",
        selected_guardrails=[],
    )
    assert result.execution_status == "Completed"
    assert result.timeline[0].status is TimelineStatus.COMPLETED
    assert result.timeline[-1].status is TimelineStatus.COMPLETED
    assert result.timeline[-1].title == "Execution completed"
    assert all(
        event.status is not TimelineStatus.RUNNING for event in result.timeline
    )
