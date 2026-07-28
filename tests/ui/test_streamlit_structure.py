from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = ROOT / "app"


def test_dashboard_uses_required_streamlit_primitives() -> None:
    source = "\n".join(path.read_text() for path in UI_ROOT.rglob("*.py"))
    for primitive in (
        "st.columns",
        "st.container",
        "st.tabs",
        "st.status",
        "st.progress",
        "st.metric",
        "st.code",
        "st.json",
        "st.session_state",
    ):
        assert primitive in source


def test_live_adapters_import_completed_production_guardrails() -> None:
    source = UI_ROOT.joinpath("services/backend_adapters.py").read_text()
    assert "from orchestrator.nodes.coordinator import coordinator_node" in source
    assert "guard_and_execute_tool_batch" in source
    assert "build_default_tool_registry" in source


def test_streamlit_version_is_python_312_compatible() -> None:
    pyproject = ROOT.joinpath("pyproject.toml").read_text()
    assert '"streamlit>=1.60,<2.0"' in pyproject
    assert 'requires-python = ">=3.12,<3.13"' in pyproject


def test_ui_has_no_subtitle_or_caption_copy() -> None:
    source = "\n".join(path.read_text() for path in UI_ROOT.rglob("*.py"))
    assert "st.caption" not in source
    assert "dashboard-subtitle" not in source
    assert "dashboard-kicker" not in source
    assert "node-meta" not in source


def test_custom_markup_uses_html_renderer_instead_of_joined_markdown() -> None:
    timeline = UI_ROOT.joinpath("components/timeline.py").read_text()
    helper = UI_ROOT.joinpath("visual_html.py").read_text()
    assert "st.markdown(\"\".join" not in timeline
    assert "render_html" in timeline
    assert "st.html" in helper


def test_responsive_css_prevents_column_and_text_overflow() -> None:
    styles = UI_ROOT.joinpath("styles.py").read_text()
    assert '[data-testid="stColumn"]' in styles
    assert "min-width: 0" in styles
    assert "overflow-wrap: anywhere" in styles
    assert "white-space: normal" in styles
