"""Worker D: deterministic full or degraded audit reporting."""

from __future__ import annotations

from contract import AgentState


def reporter_node(state: AgentState) -> dict[str, object]:
    status = "DEGRADED PARTIAL REPORT" if state.degraded_output else "COMPLETE REPORT"
    lines = [
        status,
        f"Input: {state.raw_input}",
        f"Coordinator rounds: {state.round_number}",
    ]
    if state.analysis_payload is not None:
        analysis = state.analysis_payload
        lines.extend(
            [
                f"Analysis: {analysis.ticker} {analysis.side} {analysis.quantity}",
                f"Confidence: {analysis.confidence:.2f}",
                f"Risk level: {analysis.risk_level}",
            ]
        )
    else:
        lines.append("Analysis: unavailable")

    if state.tool_execution_results:
        for result in state.tool_execution_results:
            lines.append(
                f"Mock action: {result.tool_name} -> {result.status} "
                f"({result.reference_id})"
            )
    else:
        lines.append("Mock action: none completed")

    if state.validation_result is not None:
        lines.append(f"Validation: {state.validation_result.reason}")
    if state.termination_reason:
        lines.append(f"Termination: {state.termination_reason}")
    if state.errors:
        lines.append("Errors:")
        lines.extend(f"- {error.code}: {error.message}" for error in state.errors)

    return {"final_report": "\n".join(lines)}
