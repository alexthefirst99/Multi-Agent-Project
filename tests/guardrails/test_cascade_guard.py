from __future__ import annotations

from copy import deepcopy

import pytest

from contract import AnalysisPayload
from orchestrator.guardrails.cascade_guard import (
    CascadeValidationError,
    sanitize_actor_output,
    validate_business_consistency,
)

ANALYSIS = AnalysisPayload(
    ticker="AAPL",
    side="buy",
    quantity=10,
    confidence=0.8,
    rationale="Unusual volume supports a small mocked position.",
    risk_level="medium",
)


def test_safe_values_are_sanitized_without_mutating_raw_output() -> None:
    raw = [
        {
            "tool_name": "execute_trade",
            "success": "true",
            "status": " MOCK_SUCCESS ",
            "reference_id": "mock-1",
            "ticker": " aapl ",
            "side": "buy",
            "quantity": "10",
        }
    ]
    snapshot = deepcopy(raw)
    output = sanitize_actor_output(raw)
    assert output.results[0].ticker == "AAPL"
    assert output.results[0].quantity == 10
    assert output.sanitized_values > 0
    assert raw == snapshot


def test_malformed_output_is_rejected_before_business_logic() -> None:
    with pytest.raises(CascadeValidationError):
        sanitize_actor_output([{"tool_name": "execute_trade", "quantity": "ten"}])


def test_business_mismatch_requests_rollback() -> None:
    result = sanitize_actor_output(
        [
            {
                "tool_name": "execute_trade",
                "success": True,
                "status": "mock_success",
                "reference_id": "mock-1",
                "ticker": "MSFT",
                "side": "buy",
                "quantity": 10,
            }
        ]
    ).results
    validation = validate_business_consistency(ANALYSIS, result)
    assert validation.accepted is False
    assert validation.rollback_required is True
    assert "ticker mismatch" in validation.reason


def test_matching_result_is_accepted() -> None:
    result = sanitize_actor_output(
        [
            {
                "tool_name": "execute_trade",
                "success": True,
                "status": "mock_success",
                "reference_id": "mock-1",
                "ticker": "AAPL",
                "side": "buy",
                "quantity": 10,
            }
        ]
    ).results
    assert validate_business_consistency(ANALYSIS, result).accepted is True
