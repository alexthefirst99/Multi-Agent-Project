"""Deterministic silent-hallucination failure reproduction."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from contract import AnalysisPayload
from snippet import StructuredOutputGuardError, invoke_with_one_retry

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
        self.responses = responses
        self.calls = 0

    def invoke(self, input_value: object) -> object:
        response = self.responses[self.calls]
        self.calls += 1
        return response


def append_correction(value: object, error: str) -> object:
    return [value, {"validation_error": error}]


def main() -> None:
    unsafe_payload = INVALID
    unsafe_accepted = 1 if isinstance(unsafe_payload, dict) else 0

    guarded_invoker = ScriptedInvoker([INVALID, VALID])
    guarded = invoke_with_one_retry(
        guarded_invoker,
        AnalysisPayload,
        {"prompt": "analyze"},
        append_correction=append_correction,
    )

    double_failure = ScriptedInvoker([INVALID, INVALID, VALID])
    explicit_failure = False
    try:
        invoke_with_one_retry(
            double_failure,
            AnalysisPayload,
            {"prompt": "analyze"},
            append_correction=append_correction,
        )
    except StructuredOutputGuardError:
        explicit_failure = True

    print("=== WITHOUT GUARDRAIL ===")
    print(f"Missing-ticker payload accepted: {unsafe_accepted}/1")
    print(f"Forwarded payload keys: {sorted(unsafe_payload)}")

    print("\n=== WITH GUARDRAIL ===")
    print("Missing-ticker payload forwarded: 0/1")
    print(f"Correction retries used: {guarded.retry_count}")
    print(f"Recovered ticker: {guarded.value.ticker}")
    print(f"Double failure raised explicit error: {explicit_failure}")

    print("\n=== METRICS ===")
    print("Invalid payload acceptance: 100% -> 0%")
    print("Maximum automated retries: unbounded/undefined -> exactly 1")

    assert guarded.retry_count == 1
    assert guarded.value.ticker == "AAPL"
    assert guarded_invoker.calls == 2
    assert double_failure.calls == 2
    assert explicit_failure is True


if __name__ == "__main__":
    main()
