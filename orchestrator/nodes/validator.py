"""Worker C: boundary sanitization and downstream business validation."""

from __future__ import annotations

from contract import AgentState, GraphError, ValidationResult
from orchestrator.guardrails.cascade_guard import (
    CascadeValidationError,
    sanitize_actor_output,
    validate_business_consistency,
)


def validator_node(state: AgentState) -> dict[str, object]:
    errors = list(state.errors)
    if state.analysis_payload is None:
        reason = "Validator received no structured analysis."
        errors.append(
            GraphError(
                code="business_validation_error",
                message=reason,
                node="worker_c_validator",
                recoverable=True,
            )
        )
        return {
            "validation_result": ValidationResult(
                accepted=False,
                rollback_required=True,
                reason=reason,
            ),
            "rejection_flag": True,
            "rejection_reason": reason,
            "rollback_requested": True,
            "is_validated": False,
            "errors": errors,
        }

    # Analyzer output reaches Worker C first. It is already a typed contract
    # object, so this pass only confirms readiness for the Actor.
    if not state.pending_actor_output:
        if state.rejection_flag:
            return {
                "validation_result": ValidationResult(
                    accepted=False,
                    rollback_required=True,
                    reason=state.rejection_reason or "Upstream guardrail rejected the action.",
                ),
                "is_validated": False,
                "errors": errors,
            }
        return {
            "validation_result": ValidationResult(
                accepted=True,
                rollback_required=False,
                reason="Structured analysis is safe to pass to the Actor.",
                checked_items=1,
            ),
            "rejection_flag": False,
            "rejection_reason": None,
            "rollback_requested": False,
            "is_validated": False,
            "errors": errors,
        }

    try:
        sanitized = sanitize_actor_output(state.pending_actor_output)
    except CascadeValidationError as exc:
        errors.append(
            GraphError(
                code="malformed_actor_output",
                message=str(exc),
                node="worker_c_validator",
                recoverable=True,
            )
        )
        return {
            "tool_execution_results": [],
            "validation_result": ValidationResult(
                accepted=False,
                rollback_required=True,
                reason=str(exc),
                checked_items=len(state.pending_actor_output),
            ),
            "rejection_flag": True,
            "rejection_reason": str(exc),
            "rollback_requested": True,
            "is_validated": False,
            "termination_reason": "cascade_rejection",
            "errors": errors,
        }

    validation = validate_business_consistency(
        state.analysis_payload,
        sanitized.results,
    )
    if not validation.accepted:
        errors.append(
            GraphError(
                code="business_validation_error",
                message=validation.reason,
                node="worker_c_validator",
                recoverable=True,
            )
        )
    return {
        "tool_execution_results": list(sanitized.results),
        "pending_actor_output": [],
        "validation_result": validation,
        "rejection_flag": not validation.accepted,
        "rejection_reason": None if validation.accepted else validation.reason,
        "rollback_requested": validation.rollback_required,
        "is_validated": validation.accepted,
        "errors": errors,
    }
