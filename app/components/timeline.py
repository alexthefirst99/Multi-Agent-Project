"""Responsive, timeline-first execution renderer."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

import streamlit as st

from app.models import TimelineEvent, TimelineStatus
from app.visual_html import render_html

_BADGE_COLORS = {
    TimelineStatus.RUNNING: "blue",
    TimelineStatus.STILL_RUNNING: "red",
    TimelineStatus.STOPPED: "gray",
    TimelineStatus.COMPLETED: "green",
    TimelineStatus.REJECTED: "red",
    TimelineStatus.ROLLED_BACK: "orange",
    TimelineStatus.GUARDRAIL_TRIGGERED: "orange",
    TimelineStatus.FORCED_ROUTE: "orange",
    TimelineStatus.FAILED: "red",
    TimelineStatus.SAFE_EXIT: "green",
}

_MARKER_CLASSES = {
    TimelineStatus.RUNNING: "running",
    TimelineStatus.STILL_RUNNING: "failed",
    TimelineStatus.STOPPED: "waiting",
    TimelineStatus.COMPLETED: "completed",
    TimelineStatus.REJECTED: "failed",
    TimelineStatus.ROLLED_BACK: "guarded",
    TimelineStatus.GUARDRAIL_TRIGGERED: "guarded",
    TimelineStatus.FORCED_ROUTE: "guarded",
    TimelineStatus.FAILED: "failed",
    TimelineStatus.SAFE_EXIT: "completed",
}


def _state_change_line(event: TimelineEvent) -> str:
    return "  ·  ".join(
        f"{key} = {value!r}" if isinstance(value, str) else f"{key} = {value}"
        for key, value in event.state_changes.items()
    )


def render_timeline(events: Sequence[TimelineEvent]) -> None:
    st.subheader("Execution Timeline")
    if not events:
        st.info("Run a demonstration to populate the unified execution timeline.")
        return

    for event in events:
        with st.container(border=True, key=f"timeline_event_{event.sequence}"):
            metadata, content, status = st.columns(
                [0.16, 0.62, 0.22],
                vertical_alignment="top",
            )
            with metadata:
                marker_class = _MARKER_CLASSES[event.status]
                render_html(
                    f'<span class="timeline-marker {marker_class}" '
                    f'aria-label="{escape(event.status.value)}"></span>'
                )
                st.markdown(f"**{event.sequence:02d} · {event.timestamp}**")
                st.write(event.source)
            with content:
                st.markdown(f"**{event.title}**")
                st.write(event.detail)
                if event.state_changes:
                    st.code(
                        _state_change_line(event),
                        language=None,
                        wrap_lines=True,
                    )
            with status:
                st.badge(event.status.value, color=_BADGE_COLORS[event.status])
