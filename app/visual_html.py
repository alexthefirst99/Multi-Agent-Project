"""Small, self-contained HTML visuals used by native Streamlit components."""

from __future__ import annotations

from textwrap import dedent

import streamlit as st


def render_html(markup: str) -> None:
    """Render compact decorative markup without Markdown's HTML parser."""
    st.html(dedent(markup).strip())
