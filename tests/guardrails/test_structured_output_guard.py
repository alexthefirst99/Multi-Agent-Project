from __future__ import annotations

from copy import deepcopy

import pytest

from contract import AnalysisPayload
from orchestrator.guardrails.structured_output_guard import (
    StructuredOutputGuardError,
    invoke_with_one_retry,
)

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

    def invoke(self, input_value: object) -> object:
        response = self.responses[self.calls]
        self.calls += 1
        return response


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
