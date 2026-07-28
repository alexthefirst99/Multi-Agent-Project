"""Session-state helpers for the Streamlit application."""

from __future__ import annotations

from typing import Any

from app.mock_data import (
    DEFAULT_INJECTED_FAILURES,
    EXAMPLE_PROMPTS,
    FAILURES,
    GUARDRAILS,
)


def guardrail_key(guardrail: str) -> str:
    return "guardrail_tick_" + guardrail.lower().replace(" ", "_")


def failure_tick_key(failure: str) -> str:
    return "failure_tick_" + failure.lower().replace(" ", "_")


def _set_failure_ticks(
    session_state: Any,
    selected: list[str] | tuple[str, ...],
) -> None:
    selected_set = set(selected)
    for failure in FAILURES:
        session_state[failure_tick_key(failure)] = failure in selected_set
    session_state["injected_failures"] = list(selected)


def _set_guardrail_ticks(
    session_state: Any,
    selected: list[str] | tuple[str, ...],
) -> None:
    selected_set = set(selected)
    for guardrail in GUARDRAILS:
        session_state[guardrail_key(guardrail)] = guardrail in selected_set
    session_state["active_guardrails"] = list(selected)


def initialize_state(session_state: Any) -> None:
    defaults = {
        "prompt_input": EXAMPLE_PROMPTS[0],
        "selected_scenario": "Happy Path",
        "injected_failures": [],
        "selected_guardrail": "No Injected Failure",
        "active_guardrails": [],
        "execution_mode": "WITHOUT Guardrail",
        "result": None,
        "timeline_events": (),
        "execution_summary": None,
        "active_tab_data": {},
        "is_running": False,
        "run_status": "Ready",
    }
    for key, value in defaults.items():
        if key not in session_state:
            session_state[key] = value
    if not any(failure_tick_key(item) in session_state for item in FAILURES):
        _set_failure_ticks(session_state, [])
    if not any(guardrail_key(item) in session_state for item in GUARDRAILS):
        _set_guardrail_ticks(session_state, [])


def selected_failures(session_state: Any) -> tuple[str, ...]:
    return tuple(
        failure
        for failure in FAILURES
        if session_state.get(failure_tick_key(failure), False)
    )


def selected_guardrails(session_state: Any) -> tuple[str, ...]:
    return tuple(
        guardrail
        for guardrail in GUARDRAILS
        if session_state.get(guardrail_key(guardrail), False)
    )


def choose_prompt(session_state: Any, prompt: str) -> None:
    session_state["prompt_input"] = prompt


def sync_scenario_defaults(session_state: Any) -> None:
    scenario = session_state["selected_scenario"]
    if scenario == "Multiple Failures":
        injected = list(session_state.get("injected_failures") or ())
        if len(injected) < 2:
            injected = list(DEFAULT_INJECTED_FAILURES)
        _set_failure_ticks(session_state, injected)
        session_state["injected_failures"] = injected
        return
    if scenario == "Happy Path":
        _set_failure_ticks(session_state, [])
    else:
        _set_failure_ticks(session_state, [scenario])


def sync_injected_guardrails(session_state: Any) -> None:
    _set_failure_ticks(session_state, session_state["injected_failures"])


def sync_failure_ticks(session_state: Any) -> None:
    failures = list(selected_failures(session_state))
    session_state["injected_failures"] = failures
    session_state["selected_scenario"] = (
        "Happy Path"
        if not failures
        else failures[0]
        if len(failures) == 1
        else "Multiple Failures"
    )


def sync_guardrail_ticks(session_state: Any) -> None:
    active = list(selected_guardrails(session_state))
    session_state["active_guardrails"] = active
    session_state["execution_mode"] = (
        "WITH Guardrail" if active else "WITHOUT Guardrail"
    )
    session_state["selected_guardrail"] = (
        active[0] if len(active) == 1 else "No Injected Failure"
    )


def reset_dashboard(session_state: Any) -> None:
    session_state["prompt_input"] = EXAMPLE_PROMPTS[0]
    session_state["selected_scenario"] = "Happy Path"
    session_state["injected_failures"] = []
    session_state["selected_guardrail"] = "No Injected Failure"
    session_state["active_guardrails"] = []
    _set_failure_ticks(session_state, [])
    _set_guardrail_ticks(session_state, [])
    session_state["execution_mode"] = "WITHOUT Guardrail"
    session_state["result"] = None
    session_state["timeline_events"] = ()
    session_state["execution_summary"] = None
    session_state["active_tab_data"] = {}
    session_state["is_running"] = False
    session_state["run_status"] = "Ready"
