"""Page header and its single set of run controls."""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_header(session_state: Any) -> tuple[bool, bool]:
    title_col, run_col = st.columns(
        [0.78, 0.22],
        vertical_alignment="center",
    )
    with title_col:
        st.title("Multi-Agent Guardrail Control Center")
    with run_col:
        if session_state["is_running"]:
            stop_clicked = st.button(
                "Stop",
                type="primary",
                width="stretch",
                key="header_stop",
            )
            run_clicked = False
        else:
            run_clicked = st.button(
                "Run Demonstration",
                type="primary",
                width="stretch",
                disabled=not session_state["prompt_input"].strip(),
                key="header_run",
            )
            stop_clicked = False
    return run_clicked, stop_clicked
