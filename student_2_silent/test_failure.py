"""Deterministic Worker A silent-hallucination failure reproduction.

This script uses scripted in-memory model responses only. It first runs an
intentionally unguarded Analyzer that accepts any dictionary, then runs the
production Worker A node with the structured-output guardrail enabled.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from contract import AgentState, AnalysisPayload
from student_2_silent.snippet import make_analyzer_node

VALID = {
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10,
    "confidence": 0.8,
    "rationale": "Unusual volume supports a small mocked position.",
    "risk_level": "medium",
}
INVALID = {key: value for key, value in VALID.items() if key != "ticker"}


class ScriptedInvoker:
    """A deterministic stand-in for an LLM; it never performs network I/O."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.inputs: list[object] = []

    def invoke(self, input_value: object) -> object:
        self.inputs.append(input_value)
        response = self.responses[self.calls]
        self.calls += 1
        return response


class ScriptedChatModel:
    """Records the schema Worker A requests before returning the fake invoker."""

    def __init__(self, responses: list[object]) -> None:
        self.structured_model = ScriptedInvoker(responses)
        self.requested_schema: object | None = None

    def with_structured_output(self, schema: object) -> ScriptedInvoker:
        self.requested_schema = schema
        return self.structured_model


def unguarded_analyzer_node(
    state: AgentState, raw_model: ScriptedInvoker
) -> dict[str, object]:
    """Broken baseline: dictionary shape is trusted without contract parsing."""
    response = raw_model.invoke([{"role": "user", "content": state.raw_input}])
    return {"analysis_payload": response}


def build_messages(state: AgentState) -> list[object]:
    return [{"role": "user", "content": state.raw_input}]


def append_correction(input_value: object, error: str) -> object:
    assert isinstance(input_value, list)
    return [
        *input_value,
        {
            "role": "user",
            "content": f"Correct the schema once. Validation error: {error}",
        },
    ]


def main() -> None:
    state = AgentState(raw_input="Analyze unusual AAPL volume for a mock trade.")
    stale_state = AgentState(
        raw_input=state.raw_input,
        pending_tool_calls=[{"stale": "must not survive"}],
        pending_actor_output=[{"stale": "must not survive"}],
    )

    raw_model = ScriptedInvoker([INVALID])
    unsafe_updates = unguarded_analyzer_node(stale_state, raw_model)
    unsafe_accepted = int(isinstance(unsafe_updates["analysis_payload"], dict))
    unsafe_stale_groups_retained = sum(
        bool(group)
        for group in (
            stale_state.pending_tool_calls,
            stale_state.pending_actor_output,
        )
    )

    recovering_model = ScriptedChatModel([INVALID, VALID])
    recovering_node = make_analyzer_node(
        recovering_model,
        message_builder=build_messages,
        correction_builder=append_correction,
    )
    recovered_updates = recovering_node(state)
    recovered_payload = recovered_updates["analysis_payload"]
    retry_input = recovering_model.structured_model.inputs[1]
    assert isinstance(retry_input, list)
    correction_received = "ticker" in retry_input[-1]["content"]

    failing_model = ScriptedChatModel([INVALID, INVALID, VALID])
    failing_node = make_analyzer_node(
        failing_model,
        message_builder=build_messages,
        correction_builder=append_correction,
    )
    failure_updates = failing_node(stale_state)
    stale_outputs_cleared = (
        failure_updates["pending_tool_calls"] == []
        and failure_updates["pending_actor_output"] == []
    )

    print("=== WITHOUT GUARDRAIL ===")
    print("Structured schema requested: no")
    print(f"Missing-ticker payload accepted: {unsafe_accepted}/1")
    print(f"Forwarded payload keys: {sorted(unsafe_updates['analysis_payload'])}")
    print(f"Stale downstream payload groups retained: {unsafe_stale_groups_retained}/2")

    print("\n=== WITH GUARDRAIL ===")
    print(f"Requested schema: {recovering_model.requested_schema.__name__}")
    print("Missing-ticker payload forwarded: 0/1")
    print(f"Correction retries used: {recovered_updates['analysis_retry_count']}")
    print(f"Validation error returned to retry: {correction_received}")
    print(f"Recovered ticker: {recovered_payload.ticker}")
    print(f"Double-failure model calls: {failing_model.structured_model.calls}")
    print(f"analysis_schema_error flag: {failure_updates['analysis_schema_error']}")
    print(
        "Incomplete payload after double failure: "
        f"{failure_updates['analysis_payload']}"
    )
    print(f"Stale downstream outputs cleared: {stale_outputs_cleared}")

    print("\n=== METRICS ===")
    print("Invalid payload acceptance: 100% -> 0%")
    print("Invalid outputs returned as analysis_payload: 1/1 -> 0/2")
    print("Automated self-correction attempts: 0 -> 1 maximum")
    print("Model calls before Analyzer returns: 1 -> 2 maximum")
    print("Explicit schema-error state on double failure: 0/1 -> 1/1")
    print("Stale downstream payload groups retained: 2/2 -> 0/2")

    assert unsafe_accepted == 1
    assert unsafe_stale_groups_retained == 2
    assert recovering_model.requested_schema is AnalysisPayload
    assert isinstance(recovered_payload, AnalysisPayload)
    assert recovered_payload.ticker == "AAPL"
    assert recovered_updates["analysis_retry_count"] == 1
    assert recovered_updates["analysis_schema_error"] is False
    assert recovering_model.structured_model.calls == 2
    assert correction_received is True
    assert failing_model.structured_model.calls == 2
    assert failure_updates["analysis_payload"] is None
    assert failure_updates["analysis_schema_error"] is True
    assert failure_updates["errors"][-1].code == "analysis_schema_error"
    assert stale_outputs_cleared is True


if __name__ == "__main__":
    main()
