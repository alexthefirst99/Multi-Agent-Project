"""Command-line entry point for the integrated mock orchestrator."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from contract import AgentState, MessageRecord
from orchestrator.config import (
    AppSettings,
    automatic_tracing_disabled,
    load_settings,
)
from orchestrator.graph import build_graph, build_runtime_dependencies


def run_system(raw_input: str, *, settings: AppSettings | None = None) -> AgentState:
    """Build and invoke the graph for one unstructured input."""
    resolved_settings = settings or load_settings()
    dependencies = build_runtime_dependencies(resolved_settings)
    graph = build_graph(dependencies)
    initial_state = AgentState(
        raw_input=raw_input,
        messages=[
            MessageRecord(
                role="system",
                kind="system_instruction",
                content=(
                    "All external actions are mocked. Apply every deterministic "
                    "guardrail before reporting."
                ),
            ),
            MessageRecord(role="user", content=raw_input),
        ],
    )
    with automatic_tracing_disabled():
        result = graph.invoke(initial_state)
    return result if isinstance(result, AgentState) else AgentState.model_validate(result)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments, run the graph, and print the final report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="AAPL rose 4% in ten minutes on unusual volume; consider 10 shares.",
        help="Unstructured market signal for the orchestrator.",
    )
    args = parser.parse_args(argv)
    final_state = run_system(args.input)
    print(final_state.final_report or "No final report was produced.")
    return 0
