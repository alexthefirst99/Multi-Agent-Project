"""Worker A: structured market-signal analysis."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from contract import AgentState, AnalysisPayload, GraphError, MessageRecord
from orchestrator.guardrails.structured_output_guard import (
    StructuredOutputGuardError,
    invoke_with_one_retry,
)

NodeCallable = Callable[[AgentState], dict[str, object]]


def _build_messages(state: AgentState) -> list[Any]:
    from langchain_core.messages import HumanMessage, SystemMessage

    system = SystemMessage(
        content=(
            "Extract one conservative, mocked financial-trading decision. "
            "Return only the requested structured schema."
        )
    )
    user_content = state.raw_input
    if state.rejection_reason:
        user_content += f"\nPrevious validation rejection: {state.rejection_reason}"
    return [system, HumanMessage(content=user_content)]


def _append_correction(input_value: object, error_text: str) -> object:
    from langchain_core.messages import HumanMessage

    if not isinstance(input_value, list):
        raise TypeError("Analyzer input must be a message list.")
    return [
        *input_value,
        HumanMessage(
            content=(
                "Your previous response failed schema validation. Correct it once. "
                f"Validation error: {error_text}"
            )
        ),
    ]


def make_analyzer_node(
    chat_model: Any,
    *,
    message_builder: Callable[[AgentState], object] = _build_messages,
    correction_builder: Callable[[object, str], object] = _append_correction,
) -> NodeCallable:
    structured_model = chat_model.with_structured_output(AnalysisPayload)

    def analyzer_node(state: AgentState) -> dict[str, object]:
        errors = list(state.errors)
        try:
            guarded = invoke_with_one_retry(
                structured_model,
                AnalysisPayload,
                message_builder(state),
                append_correction=correction_builder,
            )
        except StructuredOutputGuardError as exc:
            errors.append(
                GraphError(
                    code="analysis_schema_error",
                    message=str(exc),
                    node="worker_a_analyzer",
                    recoverable=False,
                )
            )
            return {
                "analysis_payload": None,
                "analysis_retry_count": 1,
                "analysis_schema_error": True,
                "rejection_flag": False,
                "rollback_requested": False,
                "errors": errors,
            }

        messages = list(state.messages)
        messages.append(
            MessageRecord(
                role="assistant",
                content=(
                    f"Structured analysis: {guarded.value.ticker} "
                    f"{guarded.value.side} {guarded.value.quantity}."
                ),
                name="worker_a_analyzer",
            )
        )
        return {
            "analysis_payload": guarded.value,
            "analysis_retry_count": guarded.retry_count,
            "analysis_schema_error": False,
            "pending_tool_calls": [],
            "approved_tool_calls": [],
            "pending_actor_output": [],
            "tool_execution_results": [],
            "validation_result": None,
            "rejection_flag": False,
            "rejection_reason": None,
            "rollback_requested": False,
            "is_validated": False,
            "messages": messages,
            "errors": errors,
        }

    return analyzer_node
