"""Worker C: boundary sanitization and downstream business validation.

Student 4 (JN) owns this layer as two explicit node functions:

- ``validate_sanitize_node`` sits between Worker B (Actor) and Worker C's
  business checks. It asserts contract-derived structural invariants on every
  raw Actor result and promotes survivors into the typed
  ``tool_execution_results`` field. On violation it sets the rejection flag
  and requests rollback instead of letting malformed data cascade forward.
- ``worker_c_validator_node`` cross-checks the typed action results against
  the original structured analysis before anything reaches final reporting.

The frozen contract fixes the graph to six node names, so the registered
``worker_c_validator`` graph node is ``validator_node``, which runs the two
functions in sequence at the Worker B -> Worker C boundary.
"""

from __future__ import annotations

from contract import AgentState, GraphError, ValidationResult
from orchestrator.guardrails.cascade_guard import (
    CascadeValidationError,
    sanitize_actor_output,
    validate_business_consistency,
)


def validate_sanitize_node(state: AgentState) -> dict[str, object]:
    """Intercept raw Actor output at the Worker B -> Worker C boundary."""
    if not state.pending_actor_output:
        return {}

    try:
        sanitized = sanitize_actor_output(state.pending_actor_output)
    except CascadeValidationError as exc:
        errors = list(state.errors)
        errors.append(
            GraphError(
                code="malformed_actor_output",
                message=str(exc),
                node="worker_c_validator",
                recoverable=True,
            )
        )
        return {
            # Roll back: discard the malformed batch so nothing downstream
            # can observe it, and flag the Coordinator to re-route.
            "tool_execution_results": [],
            "pending_actor_output": [],
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

    # Promotion into the authoritative typed field. ``pending_actor_output``
    # is intentionally kept until the business check runs: it marks that this
    # cycle carries Actor output rather than Analyzer output.
    return {"tool_execution_results": list(sanitized.results)}


def worker_c_validator_node(state: AgentState) -> dict[str, object]:
    """Cross-check typed action results against the original analysis."""
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

    validation = validate_business_consistency(
        state.analysis_payload,
        state.tool_execution_results,
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
        "tool_execution_results": list(state.tool_execution_results),
        "pending_actor_output": [],
        "validation_result": validation,
        "rejection_flag": not validation.accepted,
        "rejection_reason": None if validation.accepted else validation.reason,
        "rollback_requested": validation.rollback_required,
        "is_validated": validation.accepted,
        "errors": errors,
    }


def validator_node(state: AgentState) -> dict[str, object]:
    """Registered ``worker_c_validator`` node: sanitize, then business-validate."""
    sanitize_updates = validate_sanitize_node(state)
    if sanitize_updates.get("rejection_flag"):
        return sanitize_updates
    merged = state.model_copy(update=sanitize_updates) if sanitize_updates else state
    return {**sanitize_updates, **worker_c_validator_node(merged)}


__all__ = ["validate_sanitize_node", "validator_node", "worker_c_validator_node"]
