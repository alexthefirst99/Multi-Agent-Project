"""Sanitize Actor output before downstream business validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from pydantic import JsonValue, ValidationError

from contract import AnalysisPayload, ToolExecutionResult, ValidationResult


class CascadeValidationError(ValueError):
    """Raised when raw Actor output cannot safely enter authoritative state."""

    def __init__(self, index: int, reason: str) -> None:
        super().__init__(f"Actor output at index {index} was rejected: {reason}")
        self.index = index
        self.reason = reason


@dataclass(frozen=True, slots=True)
class SanitizedActorOutput:
    results: tuple[ToolExecutionResult, ...]
    sanitized_values: int


def _safe_normalize_mapping(value: Mapping[str, object]) -> tuple[dict[str, object], int]:
    normalized: dict[str, object] = {}
    changes = 0
    for key, raw in value.items():
        clean = raw
        if isinstance(raw, str):
            stripped = raw.strip()
            clean = stripped
            if stripped != raw:
                changes += 1
            if key == "ticker":
                upper = stripped.upper()
                if upper != stripped:
                    changes += 1
                clean = upper
            elif key == "status":
                lower = stripped.lower()
                if lower != stripped:
                    changes += 1
                clean = lower
            elif key == "success" and stripped.lower() in {"true", "false"}:
                clean = stripped.lower() == "true"
                changes += 1
            elif key == "quantity" and stripped.isdigit():
                clean = int(stripped)
                changes += 1
        normalized[str(key)] = clean
    return normalized, changes


def sanitize_actor_output(raw_results: Sequence[JsonValue]) -> SanitizedActorOutput:
    """Parse untrusted Actor output and return typed results without mutation."""
    sanitized: list[ToolExecutionResult] = []
    total_changes = 0
    for index, raw_result in enumerate(raw_results):
        if not isinstance(raw_result, Mapping):
            raise CascadeValidationError(index, "result must be a JSON object")
        normalized, changes = _safe_normalize_mapping(raw_result)
        try:
            result = ToolExecutionResult.model_validate(normalized)
        except ValidationError as exc:
            raise CascadeValidationError(index, str(exc)) from exc
        sanitized.append(result)
        total_changes += changes
    return SanitizedActorOutput(tuple(sanitized), total_changes)


def validate_business_consistency(
    analysis: AnalysisPayload,
    results: Sequence[ToolExecutionResult],
) -> ValidationResult:
    """Ensure the executed mock trade matches the Analyzer's typed decision."""
    trade_results = [result for result in results if result.tool_name == "execute_trade"]
    if not trade_results:
        return ValidationResult(
            accepted=False,
            rollback_required=True,
            reason="No execute_trade result was produced.",
            checked_items=len(results),
        )
    if len(trade_results) != 1:
        return ValidationResult(
            accepted=False,
            rollback_required=True,
            reason="Exactly one execute_trade result is required.",
            checked_items=len(results),
        )

    result = trade_results[0]
    mismatches: list[str] = []
    if not result.success:
        mismatches.append("mock execution reported failure")
    if result.ticker != analysis.ticker:
        mismatches.append("ticker mismatch")
    if result.side != analysis.side:
        mismatches.append("side mismatch")
    if result.quantity != analysis.quantity:
        mismatches.append("quantity mismatch")

    if mismatches:
        return ValidationResult(
            accepted=False,
            rollback_required=True,
            reason="; ".join(mismatches),
            checked_items=len(results),
        )
    return ValidationResult(
        accepted=True,
        rollback_required=False,
        reason="Actor output matches the structured analysis.",
        checked_items=len(results),
    )
