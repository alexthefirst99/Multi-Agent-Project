"""Streamlit UI for the Multi-Agent Guardrail Demonstration System."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import streamlit as st

# Streamlit executes this file as a script, so make the repository root
# available before importing the sibling ``app`` and ``orchestrator`` packages.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.components.controls import render_controls
from app.components.execution_summary import render_execution_summary
from app.components.header import render_header
from app.components.tabs import render_tabs
from app.components.timeline import render_timeline
from app.models import DemoResult, TimelineEvent, TimelineStatus
from app.services.demo_runner import run_demo
from app.state import (
    failure_tick_key,
    initialize_state,
    selected_failures,
    selected_guardrails,
)
from app.styles import inject_styles


def _append_live_loop_round() -> None:
    summary = st.session_state["execution_summary"]
    result = st.session_state["result"]
    if summary is None or result is None:
        return

    round_number = summary.current_round + 1
    events = list(st.session_state["timeline_events"])
    timestamp = datetime.now().strftime("%H:%M:%S")
    additions = (
        (
            "Coordinator",
            f"Coordinator started round {round_number}",
            "Repeated routing cycle entered without an active loop guardrail.",
            TimelineStatus.COMPLETED,
            {"round_number": round_number},
        ),
        (
            "Coordinator",
            "Routed to Analyzer",
            "The same Analyzer route was selected again.",
            TimelineStatus.COMPLETED,
            {"next_route": "worker_a_analyzer"},
        ),
        (
            "Analyzer",
            "Analyzer completed",
            "Analysis finished without resolving the repeated route.",
            TimelineStatus.COMPLETED,
            {},
        ),
        (
            "Analyzer",
            "Returned control to Coordinator",
            f"Coordinator will continue into round {round_number + 1}.",
            TimelineStatus.COMPLETED,
            {},
        ),
    )
    for source, title, detail, status, state_changes in additions:
        events.append(
            TimelineEvent(
                sequence=len(events) + 1,
                timestamp=timestamp,
                source=source,
                title=title,
                detail=detail,
                status=status,
                state_changes=state_changes,
            )
        )

    updated_summary = replace(
        summary,
        current_round=round_number,
        final_status=f"Running — round {round_number}",
    )
    agent_state = dict(result.agent_state)
    agent_state["round_number"] = round_number
    agent_state["termination_reason"] = None
    metrics = dict(result.metrics)
    metrics["Rounds executed"] = round_number
    updated_result = replace(
        result,
        timeline=tuple(events),
        summary=updated_summary,
        agent_state=agent_state,
        metrics=metrics,
        execution_status=updated_summary.final_status,
        failure_summary="The repeated route remains active without a circuit breaker.",
        final_output="Execution is still running and has not produced a final result.",
    )
    st.session_state["timeline_events"] = tuple(events)
    st.session_state["execution_summary"] = updated_summary
    st.session_state["result"] = updated_result
    st.session_state["run_status"] = updated_summary.final_status


def _stop_live_loop() -> None:
    result = st.session_state["result"]
    summary = st.session_state["execution_summary"]
    events = list(st.session_state["timeline_events"])
    if result is None or summary is None:
        return

    events.append(
        TimelineEvent(
            sequence=len(events) + 1,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            source="Presenter",
            title="Demonstration stopped",
            detail="The presenter manually stopped the unguarded infinite-loop run.",
            status=TimelineStatus.STOPPED,
            state_changes={},
        )
    )
    updated_summary = replace(summary, final_status="Stopped by User")
    updated_result = replace(
        result,
        timeline=tuple(events),
        summary=updated_summary,
        execution_status="Stopped by User",
        failure_summary="The unguarded loop stopped only after presenter intervention.",
        final_output="No final system result was produced before the manual stop.",
    )
    st.session_state["timeline_events"] = tuple(events)
    st.session_state["execution_summary"] = updated_summary
    st.session_state["result"] = updated_result
    st.session_state["is_running"] = False
    st.session_state["run_status"] = "Stopped by User"
    st.session_state["selected_scenario"] = "Infinite Loop"
    st.session_state["injected_failures"] = ["Infinite Loop"]
    st.session_state[failure_tick_key("Infinite Loop")] = True


@st.fragment(run_every=1.0)
def render_live_loop() -> None:
    if not st.session_state["is_running"]:
        render_timeline(st.session_state["timeline_events"])
        return

    _append_live_loop_round()
    render_timeline(st.session_state["timeline_events"])
    render_execution_summary(st.session_state["execution_summary"])

st.set_page_config(
    page_title="Multi-Agent Guardrail Control Center",
    page_icon="◫",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_styles()
initialize_state(st.session_state)

run_clicked, stop_clicked = render_header(st.session_state)
if stop_clicked:
    _stop_live_loop()
    st.rerun()

run_feedback = st.empty()
render_controls(st.session_state)

if run_clicked:
    prompt = st.session_state["prompt_input"].strip()
    if prompt:
        active_failures = selected_failures(st.session_state)
        current_scenario = (
            "Happy Path"
            if not active_failures
            else active_failures[0]
            if len(active_failures) == 1
            else "Multiple Failures"
        )
        st.session_state["selected_scenario"] = current_scenario
        st.session_state["injected_failures"] = list(active_failures)
        active_guardrails = selected_guardrails(st.session_state)
        unguarded_infinite_loop = (
            current_scenario == "Infinite Loop"
            and "Infinite Loop Guardrail" not in active_guardrails
        )
        st.session_state["is_running"] = True
        st.session_state["run_status"] = "Running"
        with run_feedback.container():
            with st.status("Running demonstration", expanded=True) as status:
                progress = st.progress(
                    20,
                    text="Preparing the selected scenario...",
                )
                progress.progress(
                    55,
                    text="Evaluating the selected guardrails...",
                )
                result = run_demo(
                    prompt,
                    active_failures,
                    scenario=current_scenario,
                    execution_mode=st.session_state["execution_mode"],
                    selected_guardrails=active_guardrails,
                )
                progress.progress(100, text="Timeline ready.")
                status.update(
                    label=(
                        "Infinite loop is running — use Stop below"
                        if unguarded_infinite_loop
                        else "Demonstration complete — view the timeline below"
                    ),
                    state=(
                        "running" if unguarded_infinite_loop else "complete"
                    ),
                    expanded=False,
                )
        timeline = (
            result.timeline[:-1]
            if unguarded_infinite_loop
            and result.timeline
            and result.timeline[-1].status is TimelineStatus.STILL_RUNNING
            else result.timeline
        )
        if unguarded_infinite_loop:
            result = replace(
                result,
                timeline=timeline,
                summary=replace(
                    result.summary,
                    final_status="Running — round 5",
                ),
                execution_status="Running — round 5",
            )
        st.session_state["result"] = result
        st.session_state["timeline_events"] = timeline
        st.session_state["execution_summary"] = result.summary
        st.session_state["active_tab_data"] = {
            "agent_state": result.agent_state,
            "guardrails": result.guardrails,
            "metrics": result.metrics,
            "final_report": result.final_output,
        }
        st.session_state["is_running"] = unguarded_infinite_loop
        st.session_state["run_status"] = result.execution_status
        if unguarded_infinite_loop:
            st.rerun()

result: DemoResult | None = st.session_state["result"]
if (
    st.session_state["is_running"]
    and result is not None
    and result.scenario == "Infinite Loop"
):
    render_live_loop()
else:
    render_timeline(st.session_state["timeline_events"])
    render_execution_summary(st.session_state["execution_summary"])
render_tabs(result)
