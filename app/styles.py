"""Restrained responsive styling for the Streamlit UI."""

from __future__ import annotations

import streamlit as st


CSS = """
<style>
:root {
  --ui-border: #e5e7eb;
  --ui-text: #111827;
  --ui-muted: #6b7280;
  --ui-blue: #2563eb;
  --ui-green: #15803d;
  --ui-red: #dc2626;
  --ui-amber: #d97706;
}
* {
  box-sizing: border-box;
}
.stApp {
  background: #ffffff;
  color: var(--ui-text);
}
.block-container {
  max-width: 1380px;
  padding-top: 4.5rem;
  padding-bottom: 2.5rem;
}
[data-testid="stHeader"] {
  background: #ffffff;
  border-bottom: 1px solid var(--ui-border);
}
[data-testid="stColumn"],
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="stMarkdownContainer"],
[data-testid="stText"],
[data-testid="stCode"] {
  min-width: 0;
}
h1, h2, h3, p, label, code, pre, button, span {
  overflow-wrap: anywhere;
}
h1 {
  color: var(--ui-text);
  font-size: clamp(1.75rem, 3vw, 2.6rem) !important;
  line-height: 1.12 !important;
  letter-spacing: -0.035em;
  margin-bottom: 0.25rem !important;
}
h2, h3 {
  color: var(--ui-text);
  letter-spacing: -0.02em;
}
[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: var(--ui-border);
  border-radius: 12px;
  box-shadow: none;
  overflow: hidden;
}
[data-testid="stButton"] button {
  min-height: 2.5rem;
  height: auto;
  border-radius: 8px;
  font-weight: 650;
  line-height: 1.25;
  padding: 0.6rem 0.8rem;
  white-space: normal;
  overflow-wrap: anywhere;
}
[data-testid="stTextArea"] textarea {
  border-radius: 9px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
[data-testid="stSelectbox"],
[data-testid="stMultiSelect"],
[data-testid="stRadio"] {
  min-width: 0;
}
[data-testid="stMetric"] {
  min-width: 0;
  border-bottom: 1px solid var(--ui-border);
  padding-bottom: 0.75rem;
}
[data-testid="stMetricValue"] {
  color: var(--ui-text);
  font-size: clamp(1.1rem, 2vw, 1.55rem);
  line-height: 1.2;
  white-space: normal;
  overflow-wrap: anywhere;
}
[data-testid="stCode"] pre {
  margin: 0.35rem 0 0;
  padding: 0.5rem 0.65rem;
  background: #f8fafc;
  border: 1px solid #edf0f3;
  white-space: pre-wrap;
  word-break: break-word;
}
[class*="st-key-timeline_event_"] {
  border-left: 3px solid #e5e7eb;
}
[class*="st-key-timeline_event_"] p {
  margin-bottom: 0.35rem;
  line-height: 1.45;
}
.timeline-marker {
  display: inline-block;
  width: 0.55rem;
  height: 0.55rem;
  margin-right: 0.3rem;
  border-radius: 50%;
  background: #9ca3af;
}
.timeline-marker.running {
  background: var(--ui-blue);
}
.timeline-marker.completed {
  background: var(--ui-green);
}
.timeline-marker.failed {
  background: var(--ui-red);
}
.timeline-marker.guarded {
  background: var(--ui-amber);
}
.st-key-execution_summary p {
  margin-bottom: 0.2rem;
}
@media (max-width: 760px) {
  .block-container {
    padding-top: 4.25rem;
    padding-left: 0.75rem;
    padding-right: 0.75rem;
  }
  [class*="st-key-timeline_event_"] [data-testid="stHorizontalBlock"],
  .st-key-execution_summary [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  [class*="st-key-timeline_event_"] [data-testid="stColumn"],
  .st-key-execution_summary [data-testid="stColumn"] {
    flex: 1 1 12rem;
    width: auto;
  }
}
</style>
"""


def inject_styles() -> None:
    st.html(CSS)
