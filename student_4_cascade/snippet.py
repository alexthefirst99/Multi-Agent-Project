"""JN's grading view for the cascade guardrail.

The guardrail is two explicit node functions at the Worker B -> Worker C
boundary: ``validate_sanitize_node`` asserts contract-derived structural
invariants on raw Actor output, and ``worker_c_validator_node`` cross-checks
the typed results against the original analysis. ``validator_node`` is the
composition registered as the graph's ``worker_c_validator`` node.
"""

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

__all__ = [
    "ALLOWED_RESULT_STATUSES",
    "ALLOWED_RESULT_TOOL_NAMES",
    "REQUIRED_RESULT_KEYS",
    "CascadeValidationError",
    "assert_structural_invariants",
    "sanitize_actor_output",
    "validate_business_consistency",
    "validate_sanitize_node",
    "validator_node",
    "worker_c_validator_node",
]
