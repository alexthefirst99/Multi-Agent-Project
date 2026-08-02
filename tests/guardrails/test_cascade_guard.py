from __future__ import annotations

from copy import deepcopy

import pytest

from contract import AgentState, AnalysisPayload
from orchestrator.guardrails.cascade_guard import (
    ALLOWED_RESULT_STATUSES,
    ALLOWED_RESULT_TOOL_NAMES,
    REQUIRED_RESULT_KEYS,
    CascadeValidationError,
    assert_structural_invariants,
    sanitize_actor_output,
    validate_business_consistency,
)
from orchestrator.nodes.validator import (
    validate_sanitize_node,
    validator_node,
    worker_c_validator_node,
)

ANALYSIS = AnalysisPayload(
    ticker="AAPL",
    side="buy",
    quantity=10,
    confidence=0.8,
    rationale="Unusual volume supports a small mocked position.",
    risk_level="medium",
)
WELL_FORMED = {
    "tool_name": "execute_trade",
    "success": True,
    "status": "mock_success",
    "reference_id": "mock-1",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10,
}


def make_state(**overrides: object) -> AgentState:
    data: dict[str, object] = {
        "raw_input": "AAPL rose on unusual volume.",
        "analysis_payload": ANALYSIS,
    }
    data.update(overrides)
    return AgentState.model_validate(data)


def test_invariant_constants_are_derived_from_the_frozen_contract() -> None:
    assert REQUIRED_RESULT_KEYS == {"tool_name", "success", "status", "reference_id"}
    assert ALLOWED_RESULT_STATUSES == {
        "mock_success",
        "mock_cancelled",
        "mock_alerted",
        "mock_failed",
    }
    assert ALLOWED_RESULT_TOOL_NAMES == {
        "execute_trade",
        "cancel_order",
        "send_compliance_alert",
    }


def test_missing_required_keys_violate_structural_invariants() -> None:
    entry = {"tool_name": "execute_trade", "success": True}
    with pytest.raises(CascadeValidationError) as excinfo:
        assert_structural_invariants(entry, 0)
    assert "missing required keys: reference_id, status" in str(excinfo.value)


def test_status_outside_allowed_set_violates_structural_invariants() -> None:
    entry = {**WELL_FORMED, "status": "filled"}
    with pytest.raises(CascadeValidationError) as excinfo:
        assert_structural_invariants(entry, 3)
    assert "status 'filled' is not in the allowed set" in str(excinfo.value)
    assert excinfo.value.index == 3


def test_unknown_tool_name_violates_structural_invariants() -> None:
    entry = {**WELL_FORMED, "tool_name": "transfer_client_funds"}
    with pytest.raises(CascadeValidationError, match="tool_name 'transfer_client_funds'"):
        assert_structural_invariants(entry, 0)


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


@pytest.mark.parametrize(
    "entry",
    [
        {**WELL_FORMED, "tool_name": ["execute_trade"]},
        {**WELL_FORMED, "status": {"nested": 1}},
    ],
)
def test_unhashable_values_are_rejected_not_crashed(entry: dict[str, object]) -> None:
    with pytest.raises(CascadeValidationError, match="is not in the allowed set"):
        sanitize_actor_output([entry])


def test_type_violations_pass_invariants_but_fail_the_typed_backstop() -> None:
    # The backstop's Pydantic message is distinctive: it proves the entry got
    # PAST the invariant layer and was rejected by typed validation instead.
    with pytest.raises(CascadeValidationError, match="validation error"):
        sanitize_actor_output([{**WELL_FORMED, "quantity": "ten"}])


def test_business_mismatch_requests_rollback() -> None:
    result = sanitize_actor_output([{**WELL_FORMED, "ticker": "MSFT"}]).results
    validation = validate_business_consistency(ANALYSIS, result)
    assert validation.accepted is False
    assert validation.rollback_required is True
    assert "ticker mismatch" in validation.reason


def test_matching_result_is_accepted() -> None:
    result = sanitize_actor_output([WELL_FORMED]).results
    assert validate_business_consistency(ANALYSIS, result).accepted is True


def test_validate_sanitize_node_is_a_noop_without_actor_output() -> None:
    assert validate_sanitize_node(make_state()) == {}


def test_validate_sanitize_node_rejects_and_rolls_back_malformed_output() -> None:
    state = make_state(
        pending_actor_output=[{"tool_name": "execute_trade", "success": True}]
    )
    updates = validate_sanitize_node(state)
    assert updates["rejection_flag"] is True
    assert updates["rollback_requested"] is True
    assert updates["tool_execution_results"] == []
    assert updates["pending_actor_output"] == []
    assert updates["is_validated"] is False
    assert updates["termination_reason"] == "cascade_rejection"
    errors = updates["errors"]
    assert isinstance(errors, list)
    assert errors[-1].code == "malformed_actor_output"
    assert errors[-1].node == "worker_c_validator"
    # The invariant layer's message, not Pydantic's "Field required": proves
    # assert_structural_invariants is wired into the sanitize pipeline.
    assert "missing required keys: reference_id, status" in errors[-1].message


def test_validate_sanitize_node_promotes_typed_results() -> None:
    state = make_state(pending_actor_output=[dict(WELL_FORMED)])
    updates = validate_sanitize_node(state)
    results = updates["tool_execution_results"]
    assert isinstance(results, list)
    assert results[0].quantity == 10
    assert "rejection_flag" not in updates


def test_worker_c_validator_rejects_when_analysis_is_missing() -> None:
    state = AgentState(raw_input="AAPL rose on unusual volume.")
    updates = worker_c_validator_node(state)
    assert updates["rejection_flag"] is True
    assert updates["rollback_requested"] is True
    assert updates["errors"][-1].code == "business_validation_error"


def test_worker_c_validator_preserves_upstream_guardrail_rejection() -> None:
    state = make_state(
        rejection_flag=True,
        rejection_reason="tool guard rejected the batch",
        rollback_requested=True,
    )
    updates = worker_c_validator_node(state)
    assert updates["is_validated"] is False
    assert updates["validation_result"].accepted is False
    assert updates["validation_result"].rollback_required is True
    assert updates["validation_result"].reason == "tool guard rejected the batch"
    # The precheck must not touch the upstream flags: they stay set in state
    # so the Coordinator re-routes to the Analyzer.
    assert "rejection_flag" not in updates
    assert "rollback_requested" not in updates
    assert validator_node(state) == updates


def test_worker_c_validator_cross_checks_results_against_analysis() -> None:
    mismatched = sanitize_actor_output([{**WELL_FORMED, "quantity": 999}]).results
    state = make_state(
        pending_actor_output=[{**WELL_FORMED, "quantity": 999}],
        tool_execution_results=list(mismatched),
    )
    updates = worker_c_validator_node(state)
    assert updates["is_validated"] is False
    assert updates["rejection_flag"] is True
    assert updates["rollback_requested"] is True
    assert "quantity mismatch" in updates["validation_result"].reason


def test_validator_node_composes_sanitize_then_business_check() -> None:
    accepted = validator_node(make_state(pending_actor_output=[dict(WELL_FORMED)]))
    assert accepted["is_validated"] is True
    assert accepted["pending_actor_output"] == []
    assert accepted["tool_execution_results"][0].ticker == "AAPL"

    rejected = validator_node(
        make_state(pending_actor_output=[{**WELL_FORMED, "status": "filled"}])
    )
    assert rejected["rejection_flag"] is True
    assert rejected["termination_reason"] == "cascade_rejection"
    assert rejected["tool_execution_results"] == []
