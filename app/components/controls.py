"""Task, failure, and guardrail controls."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.mock_data import (
    EXAMPLE_PROMPTS,
    FAILURES,
    GUARDRAILS,
)
from app.state import (
    choose_prompt,
    failure_tick_key,
    guardrail_key,
    selected_guardrails,
    sync_failure_ticks,
    sync_guardrail_ticks,
)


def render_controls(session_state: Any) -> None:
    with st.container(border=True, key="task_input_section"):
        st.subheader("Task")
        st.text_area(
            "Task",
            key="prompt_input",
            label_visibility="collapsed",
            placeholder="Buy 10 AAPL shares because volume increased rapidly.",
            height=132,
        )
        with st.expander("Prompt suggestions"):
            suggestion_columns = st.columns(2)
            for index, prompt in enumerate(EXAMPLE_PROMPTS):
                suggestion_columns[index % 2].button(
                    prompt,
                    key=f"example_{index}",
                    width="stretch",
                    on_click=choose_prompt,
                    args=(session_state, prompt),
                )

    with st.container(border=True, key="failure_scenario_section"):
        st.subheader("Failure Scenario")
        failure_columns = st.columns(2)
        for index, failure in enumerate(FAILURES):
            failure_columns[index % 2].checkbox(
                failure,
                key=failure_tick_key(failure),
                on_change=sync_failure_ticks,
                args=(session_state,),
            )
        st.write(f"Current scenario: **{session_state['selected_scenario']}**")

    with st.container(border=True, key="guardrail_configuration_section"):
        st.subheader("Guardrail")
        guardrail_columns = st.columns(2)
        for index, guardrail in enumerate(GUARDRAILS):
            guardrail_columns[index % 2].checkbox(
                guardrail,
                key=guardrail_key(guardrail),
                on_change=sync_guardrail_ticks,
                args=(session_state,),
            )
        if (
            session_state["selected_scenario"] == "Happy Path"
            and selected_guardrails(session_state)
        ):
            st.info(
                "Guardrails are selected, but Happy Path has no injected "
                "failure to trigger them."
            )
