"""Compact execution summary renderer."""

from __future__ import annotations

import streamlit as st

from app.models import ExecutionSummary


def _value(value: object) -> str:
    if isinstance(value, tuple):
        return ", ".join(value) or "None"
    return str(value)


def render_execution_summary(summary: ExecutionSummary | None) -> None:
    st.subheader("Execution Summary")
    if summary is None:
        st.info("Summary fields will update after the first demonstration.")
        return

    fields = (
        ("Scenario", summary.scenario),
        ("Execution Mode", summary.execution_mode),
        ("Selected Guardrail", summary.selected_guardrails),
        ("Current Round", summary.current_round),
        ("Retry Count", summary.retry_count),
        ("Rollback Count", summary.rollback_count),
        ("Triggered Guardrails", summary.triggered_guardrails),
        (
            "Current Status"
            if summary.final_status.startswith("Running")
            else "Final Status",
            summary.final_status,
        ),
        ("Duration", f"{summary.duration_seconds:.2f}s"),
    )
    with st.container(border=True, key="execution_summary"):
        columns = st.columns(3)
        for index, (label, value) in enumerate(fields):
            with columns[index % 3]:
                st.markdown(f"**{label}**")
                st.write(_value(value))
