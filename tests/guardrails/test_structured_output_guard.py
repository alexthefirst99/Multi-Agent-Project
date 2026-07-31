from __future__ import annotations

from copy import deepcopy

import pytest

from contract import (
    AgentState,
    AnalysisPayload,
    ExecuteTradeArguments,
    ExecuteTradeRequest,
    ToolExecutionResult,
    ValidationResult,
)
from orchestrator.guardrails.structured_output_guard import (
    StructuredOutputGuardError,
    invoke_with_one_retry,
)
from orchestrator.nodes.analyzer import make_analyzer_node

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
    def __init__(self, responses: list[object]) -> None:
        self.structured_model = ScriptedInvoker(responses)
        self.requested_schema: object | None = None

    def with_structured_output(self, schema: object) -> ScriptedInvoker:
        self.requested_schema = schema
        return self.structured_model


def append_correction(value: object, error: str) -> object:
    assert isinstance(value, list)
    return [*value, {"correction": error}]


def test_valid_response_needs_no_retry_and_does_not_mutate_input() -> None:
    input_value = [{"prompt": "analyze"}]
    snapshot = deepcopy(input_value)
    invoker = ScriptedInvoker([VALID])
    result = invoke_with_one_retry(
        invoker,
        AnalysisPayload,
        input_value,
        append_correction=append_correction,
    )
    assert result.retry_count == 0
    assert result.value.ticker == "AAPL"
    assert input_value == snapshot


def test_invalid_first_response_gets_exactly_one_retry() -> None:
    invoker = ScriptedInvoker([INVALID, VALID])
    result = invoke_with_one_retry(
        invoker,
        AnalysisPayload,
        [],
        append_correction=append_correction,
    )
    assert result.retry_count == 1
    assert invoker.calls == 2


def test_second_failure_sets_explicit_typed_error() -> None:
    invoker = ScriptedInvoker([INVALID, INVALID, VALID])
    with pytest.raises(StructuredOutputGuardError):
        invoke_with_one_retry(
            invoker,
            AnalysisPayload,
            [],
            append_correction=append_correction,
        )
    assert invoker.calls == 2


def test_unvalidated_schema_instance_cannot_bypass_contract() -> None:
    bypass_attempt = AnalysisPayload.model_construct(
        ticker="",
        side="hold",
        quantity=-5,
        confidence=2.0,
        rationale="short",
        risk_level="extreme",
    )
    invoker = ScriptedInvoker([bypass_attempt, VALID])

    result = invoke_with_one_retry(
        invoker,
        AnalysisPayload,
        [],
        append_correction=append_correction,
    )

    assert result.retry_count == 1
    assert result.value.ticker == "AAPL"
    assert invoker.calls == 2


def test_analyzer_node_enforces_schema_and_returns_only_corrected_payload() -> None:
    model = ScriptedChatModel([INVALID, VALID])
    node = make_analyzer_node(
        model,
        message_builder=lambda state: [{"prompt": state.raw_input}],
        correction_builder=append_correction,
    )

    updates = node(AgentState(raw_input="Analyze unusual AAPL volume."))

    assert model.requested_schema is AnalysisPayload
    assert model.structured_model.calls == 2
    assert updates["analysis_retry_count"] == 1
    assert updates["analysis_schema_error"] is False
    assert isinstance(updates["analysis_payload"], AnalysisPayload)
    assert updates["analysis_payload"].ticker == "AAPL"
    retry_input = model.structured_model.inputs[1]
    assert isinstance(retry_input, list)
    assert "ticker" in retry_input[-1]["correction"]


def test_analyzer_node_flags_double_failure_and_clears_stale_outputs() -> None:
    model = ScriptedChatModel([INVALID, INVALID, VALID])
    node = make_analyzer_node(
        model,
        message_builder=lambda state: [{"prompt": state.raw_input}],
        correction_builder=append_correction,
    )
    stale_request = ExecuteTradeRequest(
        tool_name="execute_trade",
        arguments=ExecuteTradeArguments(ticker="MSFT", side="sell", quantity=3),
    )
    stale_result = ToolExecutionResult(
        tool_name="execute_trade",
        success=True,
        status="mock_success",
        reference_id="mock-stale",
        ticker="MSFT",
        side="sell",
        quantity=3,
    )
    state = AgentState(
        raw_input="Analyze unusual AAPL volume.",
        analysis_payload=AnalysisPayload.model_validate(VALID),
        pending_tool_calls=[{"stale": True}],
        approved_tool_calls=[stale_request],
        pending_actor_output=[{"stale": True}],
        tool_execution_results=[stale_result],
        validation_result=ValidationResult(
            accepted=True,
            reason="Stale result from an earlier cycle.",
            checked_items=1,
        ),
        rejection_flag=True,
        rejection_reason="Stale rejection.",
        rollback_requested=True,
        is_validated=True,
    )

    updates = node(state)

    assert model.structured_model.calls == 2
    assert updates["analysis_payload"] is None
    assert updates["analysis_retry_count"] == 1
    assert updates["analysis_schema_error"] is True
    assert updates["pending_tool_calls"] == []
    assert updates["approved_tool_calls"] == []
    assert updates["pending_actor_output"] == []
    assert updates["tool_execution_results"] == []
    assert updates["validation_result"] is None
    assert updates["rejection_flag"] is False
    assert updates["rejection_reason"] is None
    assert updates["rollback_requested"] is False
    assert updates["is_validated"] is False
    error = updates["errors"][-1]
    assert error.code == "analysis_schema_error"
    assert error.node == "worker_a_analyzer"
    assert error.recoverable is False
