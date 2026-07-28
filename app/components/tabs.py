"""Bottom result tabs."""

from __future__ import annotations

import json

import streamlit as st

from app.models import DemoResult, GuardrailStatus

_GUARDRAIL_BADGE_COLORS = {
    GuardrailStatus.ENABLED: "blue",
    GuardrailStatus.TRIGGERED: "orange",
    GuardrailStatus.NOT_TRIGGERED: "gray",
    GuardrailStatus.DISABLED: "gray",
}


def _display_value(value: object) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    if value is None:
        return "None"
    return str(value)


def _render_agent_state(result: DemoResult) -> None:
    state_rows = [
        {"Field": key, "Value": _display_value(value)}
        for key, value in result.agent_state.items()
    ]
    st.dataframe(
        state_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "Field": st.column_config.TextColumn(width="medium"),
            "Value": st.column_config.TextColumn(width="large"),
        },
    )
    with st.expander("Raw state"):
        st.json(result.agent_state, expanded=False)
        st.markdown("**Live adapter checks**")
        st.json(result.live_checks, expanded=False)


def _render_guardrails(result: DemoResult) -> None:
    views = (
        result.guardrails
        if result.scenario == "Multiple Failures"
        else tuple(
            guardrail
            for guardrail in result.guardrails
            if guardrail.title in result.selected_guardrails
        )
    )
    if not views:
        st.info("No guardrail was selected for this demonstration.")
        return

    for index, guardrail in enumerate(views):
        with st.container(border=True, key=f"guardrail_result_{index}"):
            title_col, status_col, implementation_col = st.columns(
                [0.54, 0.23, 0.23],
                vertical_alignment="center",
            )
            title_col.markdown(f"**{guardrail.title}**")
            status_col.badge(
                guardrail.status.value,
                color=_GUARDRAIL_BADGE_COLORS[guardrail.status],
            )
            implementation_col.badge(guardrail.implementation, color="gray")
            st.write(guardrail.description)
            st.markdown("**Trigger reason**")
            st.write(guardrail.trigger_reason)
            st.markdown("**Resulting action**")
            st.write(guardrail.resulting_action)


def _render_metrics(result: DemoResult) -> None:
    columns = st.columns(3)
    for index, (label, value) in enumerate(result.metrics.items()):
        with columns[index % 3]:
            st.metric(label, value)


def _render_final_report(result: DemoResult) -> None:
    selected = ", ".join(result.selected_guardrails) or "None"
    triggered = ", ".join(result.triggered_guardrails) or "None"
    outcome = result.timeline[-1].title if result.timeline else result.execution_status
    fields = (
        ("Task", result.prompt),
        ("Scenario", result.scenario),
        ("Execution Mode", result.execution_mode),
        ("Selected Guardrail", selected),
        ("Important Timeline Outcome", outcome),
        ("Guardrail Result", triggered),
        ("Final System Result", result.final_output),
    )
    with st.container(border=True):
        for label, value in fields:
            st.markdown(f"**{label}**")
            st.write(value)


def render_tabs(result: DemoResult | None) -> None:
    agent_tab, guardrail_tab, metrics_tab, report_tab = st.tabs(
        ["Agent State", "Guardrails", "Metrics", "Final Report"]
    )
    with agent_tab:
        if result is None:
            st.info("Run the system to inspect the Agent State.")
        else:
            _render_agent_state(result)
    with guardrail_tab:
        if result is None:
            st.info("Guardrail results will appear after the first run.")
        else:
            _render_guardrails(result)
    with metrics_tab:
        if result is None:
            st.info("Scenario-relevant metrics will appear after the first run.")
        else:
            _render_metrics(result)
    with report_tab:
        if result is None:
            st.info("Run the system to generate the final report.")
        else:
            _render_final_report(result)
