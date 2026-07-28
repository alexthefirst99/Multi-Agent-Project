"""Deterministic timeline adapter for live and presentation guardrail demos."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timedelta

from app.mock_data import (
    FAILURES,
    GUARDRAIL_COPY,
    GUARDRAILS,
    PIPELINE_NODES,
    SCENARIO_GUARDRAIL,
)
from app.models import (
    DemoResult,
    ExecutionSummary,
    GuardrailStatus,
    GuardrailView,
    NodeStatus,
    TimelineEvent,
    TimelineStatus,
)
from app.services.backend_adapters import (
    run_live_loop_check,
    run_live_tool_check,
)

_AFFECTED_NODE = {
    "Infinite Loop": "Coordinator",
    "Structured Output Failure": "Analyzer",
    "Rogue Tool Call": "Actor",
    "Cascade Failure": "Validator",
    "Privacy Leak": "Reporter",
    "Context Explosion": "Coordinator",
}

_LEGACY_FAILURE_NAMES = {
    "Missing Structured Field": "Structured Output Failure",
}

_TRIGGER_REASONS = {
    "Infinite Loop": "round_number reached max_rounds (5).",
    "Structured Output Failure": "Analyzer output omitted a required schema field.",
    "Rogue Tool Call": "Requested tool was not registered or authorized.",
    "Cascade Failure": "Validator rejected inconsistent Actor state.",
    "Privacy Leak": "Sensitive fields were detected before trace persistence.",
    "Context Explosion": "Estimated context size exceeded the safe threshold.",
}

_RESULTING_ACTIONS = {
    "Infinite Loop": "Forced route to Reporter with degraded partial output.",
    "Structured Output Failure": "Ran one correction retry and selected a safe route.",
    "Rogue Tool Call": "Rejected the entire tool batch before execution.",
    "Cascade Failure": "Rolled back to Coordinator and retried Actor.",
    "Privacy Leak": "Redacted sensitive fields before storing the trace.",
    "Context Explosion": "Compacted old messages and continued with reduced context.",
}


class _TimelineBuilder:
    def __init__(self) -> None:
        self._start = datetime.now().replace(microsecond=0)
        self.events: list[TimelineEvent] = []

    def add(
        self,
        source: str,
        title: str,
        detail: str,
        status: TimelineStatus,
        **state_changes: object,
    ) -> None:
        sequence = len(self.events) + 1
        self.events.append(
            TimelineEvent(
                sequence=sequence,
                timestamp=(self._start + timedelta(seconds=sequence - 1)).strftime(
                    "%H:%M:%S"
                ),
                source=source,
                title=title,
                detail=detail,
                status=status,
                state_changes=state_changes,
            )
        )


def _normalize_failures(failures: Iterable[str]) -> tuple[str, ...]:
    normalized = (
        _LEGACY_FAILURE_NAMES.get(failure, failure) for failure in failures
    )
    return tuple(
        failure
        for failure in dict.fromkeys(normalized)
        if failure in FAILURES
    )


def _render_happy_path(builder: _TimelineBuilder) -> None:
    builder.add(
        "Coordinator",
        "Execution started",
        "Coordinator accepted the task and started round 1.",
        TimelineStatus.COMPLETED,
        round_number=1,
    )
    builder.add(
        "Coordinator",
        "Routed to Analyzer",
        "The nominal analysis route was selected.",
        TimelineStatus.COMPLETED,
        next_route="worker_a_analyzer",
    )
    builder.add(
        "Analyzer",
        "Structured analysis completed",
        "The analysis payload passed schema validation.",
        TimelineStatus.COMPLETED,
        analysis_schema_error=False,
    )
    builder.add(
        "Actor",
        "Mock tool completed",
        "The authorized local mock action completed.",
        TimelineStatus.COMPLETED,
    )
    builder.add(
        "Validator",
        "Output approved",
        "Actor output matched the structured analysis.",
        TimelineStatus.COMPLETED,
        is_validated=True,
    )
    builder.add(
        "Reporter",
        "Execution completed",
        "The final report was produced through the nominal route.",
        TimelineStatus.COMPLETED,
        termination_reason="completed",
    )


def _render_loop(
    builder: _TimelineBuilder,
    *,
    mitigated: bool,
    live_rounds: int,
) -> None:
    completed_rounds = live_rounds - 1 if mitigated else 5
    for round_number in range(1, completed_rounds + 1):
        builder.add(
            "Coordinator",
            f"Coordinator started round {round_number}",
            "Repeated routing cycle entered.",
            TimelineStatus.COMPLETED,
            round_number=round_number,
        )
        builder.add(
            "Coordinator",
            "Routed to Analyzer",
            "The same Analyzer route was selected again.",
            TimelineStatus.COMPLETED,
            next_route="worker_a_analyzer",
        )
        builder.add(
            "Analyzer",
            "Analyzer completed",
            "Analysis finished without resolving the repeated route.",
            TimelineStatus.COMPLETED,
        )
        builder.add(
            "Analyzer",
            "Returned control to Coordinator",
            "Coordinator will evaluate another round.",
            TimelineStatus.RUNNING,
        )

    if mitigated:
        builder.add(
            "Coordinator",
            f"Coordinator started round {live_rounds}",
            "The configured maximum round was reached.",
            TimelineStatus.COMPLETED,
            round_number=live_rounds,
        )
        builder.add(
            "System",
            "Infinite Loop Guardrail triggered",
            "round_number reached max_rounds.",
            TimelineStatus.GUARDRAIL_TRIGGERED,
            round_number=live_rounds,
            max_rounds=5,
        )
        builder.add(
            "Coordinator",
            "Forced route to Reporter",
            "The loop guard bypassed the repeated Analyzer route.",
            TimelineStatus.FORCED_ROUTE,
            next_route="worker_d_reporter",
        )
        builder.add(
            "Reporter",
            "Degraded partial output produced",
            "Reporter preserved the available safe result.",
            TimelineStatus.COMPLETED,
            degraded_output=True,
        )
        builder.add(
            "System",
            "Safe Exit",
            "Execution stopped at the deterministic round limit.",
            TimelineStatus.SAFE_EXIT,
            termination_reason="round_limit_reached",
        )
        return

    builder.add(
        "Coordinator",
        "Still Running",
        (
            "The timeline preview paused after five rounds, but execution was not "
            "terminated because no Infinite Loop Guardrail is active."
        ),
        TimelineStatus.STILL_RUNNING,
        round_number=5,
        demo_display_limit_reached=True,
    )


def _render_structured(builder: _TimelineBuilder, *, mitigated: bool) -> None:
    builder.add(
        "Analyzer",
        "Malformed output returned",
        "The response omitted the required risk_level field.",
        TimelineStatus.FAILED,
    )
    builder.add(
        "System",
        "Missing required field",
        "The payload did not conform to AnalysisPayload.",
        TimelineStatus.REJECTED,
        analysis_schema_error=True,
    )
    if not mitigated:
        builder.add(
            "Coordinator",
            "Invalid payload forwarded",
            "The unvalidated payload entered the downstream route.",
            TimelineStatus.FAILED,
        )
        builder.add(
            "Actor",
            "Downstream failure",
            "Actor could not safely consume the malformed analysis.",
            TimelineStatus.FAILED,
        )
        return

    builder.add(
        "System",
        "Structured Output Guardrail triggered",
        "Schema validation blocked the malformed payload.",
        TimelineStatus.GUARDRAIL_TRIGGERED,
    )
    builder.add(
        "Analyzer",
        "Automated correction retry started",
        "One schema-aware retry was allowed.",
        TimelineStatus.RUNNING,
        analysis_retry_count=1,
    )
    builder.add(
        "Analyzer",
        "Correction retry succeeded",
        "The retry returned a complete structured payload.",
        TimelineStatus.COMPLETED,
        analysis_schema_error=False,
    )
    builder.add(
        "Coordinator",
        "Safe route selected",
        "The validated payload was accepted for the next stage.",
        TimelineStatus.SAFE_EXIT,
        next_route="worker_b_actor",
    )


def _render_rogue(builder: _TimelineBuilder, *, mitigated: bool, message: str) -> None:
    builder.add(
        "Actor",
        "Unauthorized tool requested",
        "Actor requested delete_production_database in the safe demo harness.",
        TimelineStatus.RUNNING,
    )
    if not mitigated:
        builder.add(
            "Tool System",
            "Tool execution proceeded",
            "The demonstration bypassed authorization checks.",
            TimelineStatus.FAILED,
        )
        builder.add(
            "Tool System",
            "Unsafe action executed",
            "The baseline records one simulated unauthorized execution; no real action ran.",
            TimelineStatus.FAILED,
            unauthorized_execution_count=1,
        )
        builder.add(
            "System",
            "Failure",
            "The unauthorized request was not contained.",
            TimelineStatus.FAILED,
        )
        return

    builder.add(
        "Tool System",
        "Tool Authorization Guardrail evaluated request",
        "The live atomic validator checked name, schema, and registration.",
        TimelineStatus.RUNNING,
    )
    builder.add(
        "Tool System",
        "Tool rejected",
        message,
        TimelineStatus.REJECTED,
    )
    builder.add(
        "Tool System",
        "Unauthorized execution count remained zero",
        "The entire tool batch was rejected before any handler ran.",
        TimelineStatus.GUARDRAIL_TRIGGERED,
        unauthorized_execution_count=0,
    )
    builder.add(
        "Coordinator",
        "Safe fallback selected",
        "Execution exited without running the unauthorized tool.",
        TimelineStatus.SAFE_EXIT,
    )


def _render_cascade(builder: _TimelineBuilder, *, mitigated: bool) -> None:
    builder.add(
        "Actor",
        "Actor completed with invalid state" if not mitigated else "Actor completed",
        "The simulated Actor result does not match the structured analysis.",
        TimelineStatus.COMPLETED,
    )
    builder.add(
        "Validator",
        "Validator started",
        "Validator inspected the Actor result.",
        TimelineStatus.RUNNING,
    )
    builder.add(
        "Validator",
        "Validation failed",
        "The output was rejected for a business consistency mismatch.",
        TimelineStatus.REJECTED,
        rejection_flag=True,
    )
    if not mitigated:
        builder.add(
            "Coordinator",
            "Rejection propagated",
            "No rollback route intercepted the rejected state.",
            TimelineStatus.FAILED,
        )
        builder.add(
            "Reporter",
            "Downstream execution failed",
            "The invalid state continued into reporting.",
            TimelineStatus.FAILED,
        )
        builder.add(
            "System",
            "Cascade failure",
            "The original rejection caused a downstream failure.",
            TimelineStatus.FAILED,
        )
        return

    builder.add(
        "Validator",
        "Rollback required",
        "Validator marked the state for rollback.",
        TimelineStatus.GUARDRAIL_TRIGGERED,
        rollback_required=True,
    )
    builder.add(
        "Validator",
        "Rollback requested",
        "Control returned to Coordinator.",
        TimelineStatus.ROLLED_BACK,
        rollback_requested=True,
    )
    builder.add(
        "Coordinator",
        "Coordinator received Rollback",
        "Coordinator selected the Actor Retry route.",
        TimelineStatus.ROLLED_BACK,
    )
    builder.add(
        "Coordinator",
        "Routed to Actor Retry",
        "One safe retry was scheduled.",
        TimelineStatus.FORCED_ROUTE,
        retry_count=1,
    )
    builder.add(
        "Actor",
        "Actor Retry completed",
        "The corrected mock result now matches the analysis.",
        TimelineStatus.COMPLETED,
    )
    builder.add(
        "Validator",
        "Validator approved Retry",
        "The corrected Actor result passed validation.",
        TimelineStatus.COMPLETED,
        is_validated=True,
    )
    builder.add(
        "Coordinator",
        "Coordinator routed to Reporter",
        "Validation succeeded after Rollback and Retry.",
        TimelineStatus.FORCED_ROUTE,
        next_route="worker_d_reporter",
    )
    builder.add(
        "Reporter",
        "Safe completion",
        "Reporter produced a validated final result.",
        TimelineStatus.SAFE_EXIT,
        termination_reason="completed",
    )


def _render_privacy(builder: _TimelineBuilder, *, mitigated: bool) -> None:
    builder.add(
        "Reporter",
        "Sensitive content entered trace payload",
        "Safe placeholders represent fields that would require protection.",
        TimelineStatus.RUNNING,
        demonstrated_fields="[EMAIL REDACTED], [API TOKEN REDACTED]",
    )
    if not mitigated:
        builder.add(
            "Trace System",
            "Sensitive fields not intercepted",
            "Without redaction, unredacted values would have been exposed; none are displayed.",
            TimelineStatus.FAILED,
        )
        builder.add(
            "Trace System",
            "Unsafe trace persisted",
            "The baseline records two simulated exposed fields.",
            TimelineStatus.FAILED,
            sensitive_fields_exposed=2,
        )
        return

    builder.add(
        "Trace System",
        "Sensitive field detected",
        "The privacy filter identified email and token-shaped values.",
        TimelineStatus.RUNNING,
    )
    builder.add(
        "Trace System",
        "Privacy Guardrail triggered",
        "Sensitive fields were intercepted before persistence.",
        TimelineStatus.GUARDRAIL_TRIGGERED,
    )
    builder.add(
        "Trace System",
        "Field redacted",
        "[EMAIL REDACTED] and [API TOKEN REDACTED] replaced sensitive values.",
        TimelineStatus.COMPLETED,
        privacy_redaction_count=2,
    )
    builder.add(
        "Trace System",
        "Sanitized trace stored",
        "Only the redacted demonstration payload was retained.",
        TimelineStatus.COMPLETED,
    )
    builder.add(
        "Reporter",
        "Execution continued safely",
        "Tracing completed without exposing the protected fields.",
        TimelineStatus.SAFE_EXIT,
    )


def _render_context(builder: _TimelineBuilder, *, mitigated: bool) -> None:
    builder.add(
        "Context Manager",
        "Context size increasing",
        "Repeated messages accumulated across coordinator rounds.",
        TimelineStatus.RUNNING,
        estimated_tokens=8200,
    )
    builder.add(
        "Context Manager",
        "Repeated message accumulation",
        "Obsolete tool outputs remained in history.",
        TimelineStatus.RUNNING,
        estimated_tokens=11200,
    )
    builder.add(
        "Context Manager",
        "Safe threshold exceeded",
        "The estimated context reached 14,500 tokens.",
        TimelineStatus.FAILED if not mitigated else TimelineStatus.RUNNING,
        estimated_tokens=14500,
    )
    if not mitigated:
        builder.add(
            "System",
            "Context failure",
            "The oversized context caused simulated excessive cost and failure.",
            TimelineStatus.FAILED,
        )
        return

    builder.add(
        "Context Manager",
        "Context Window Guardrail triggered",
        "The context threshold activated compaction.",
        TimelineStatus.GUARDRAIL_TRIGGERED,
    )
    builder.add(
        "Context Manager",
        "Old messages summarized",
        "Obsolete messages were removed and older history was summarized.",
        TimelineStatus.COMPLETED,
        pruned_messages=18,
        summarized_messages=12,
    )
    builder.add(
        "Context Manager",
        "Context size reduced",
        "The estimated context was reduced to 5,200 tokens.",
        TimelineStatus.COMPLETED,
        estimated_tokens=5200,
    )
    builder.add(
        "Coordinator",
        "Execution continued",
        "The compacted context remained within the safe threshold.",
        TimelineStatus.SAFE_EXIT,
    )


def _render_multiple(
    builder: _TimelineBuilder,
    failures: tuple[str, ...],
    mitigated: dict[str, bool],
    *,
    tool_message: str,
) -> None:
    builder.add(
        "Coordinator",
        "Integrated execution started",
        "One shared timeline will capture every injected failure.",
        TimelineStatus.RUNNING,
        round_number=1,
    )
    ordered = (
        "Structured Output Failure",
        "Context Explosion",
        "Rogue Tool Call",
        "Cascade Failure",
        "Infinite Loop",
        "Privacy Leak",
    )
    for failure in ordered:
        if failure not in failures:
            continue
        guarded = mitigated[failure]
        if failure == "Structured Output Failure":
            builder.add(
                "Analyzer",
                "Malformed schema returned",
                "The Analyzer omitted a required field.",
                TimelineStatus.FAILED,
            )
            if guarded:
                builder.add(
                    "System",
                    "Structured Output Guardrail triggered",
                    "Schema validation stopped the payload.",
                    TimelineStatus.GUARDRAIL_TRIGGERED,
                )
                builder.add(
                    "Analyzer",
                    "Analyzer Retry succeeded",
                    "The corrected payload passed validation.",
                    TimelineStatus.COMPLETED,
                    analysis_retry_count=1,
                )
            else:
                builder.add(
                    "Coordinator",
                    "Invalid schema forwarded",
                    "No matching guardrail contained the payload.",
                    TimelineStatus.FAILED,
                )
        elif failure == "Context Explosion":
            builder.add(
                "Context Manager",
                "Context threshold reached",
                "Estimated context grew to 14,500 tokens.",
                TimelineStatus.RUNNING,
            )
            if guarded:
                builder.add(
                    "Context Manager",
                    "Context Window Guardrail triggered",
                    "Old messages were summarized; context fell to 5,200 tokens.",
                    TimelineStatus.GUARDRAIL_TRIGGERED,
                )
            else:
                builder.add(
                    "Context Manager",
                    "Context remained oversized",
                    "No compaction ran.",
                    TimelineStatus.FAILED,
                )
        elif failure == "Rogue Tool Call":
            builder.add(
                "Actor",
                "Unauthorized tool requested",
                "Actor requested a tool outside the registry.",
                TimelineStatus.RUNNING,
            )
            if guarded:
                builder.add(
                    "Tool System",
                    "Tool Authorization Guardrail rejected request",
                    tool_message,
                    TimelineStatus.GUARDRAIL_TRIGGERED,
                    unauthorized_execution_count=0,
                )
            else:
                builder.add(
                    "Tool System",
                    "Unauthorized tool executed",
                    "One simulated unauthorized execution was recorded.",
                    TimelineStatus.FAILED,
                    unauthorized_execution_count=1,
                )
        elif failure == "Cascade Failure":
            builder.add(
                "Validator",
                "Validator rejected state",
                "Actor output failed consistency validation.",
                TimelineStatus.REJECTED,
                rejection_flag=True,
            )
            if guarded:
                builder.add(
                    "Validator",
                    "Rollback requested",
                    "Rollback Guardrail returned control to Coordinator.",
                    TimelineStatus.ROLLED_BACK,
                    rollback_required=True,
                )
                builder.add(
                    "Coordinator",
                    "Coordinator routed to Actor Retry",
                    "The Actor Retry completed with corrected state.",
                    TimelineStatus.FORCED_ROUTE,
                    retry_count=1,
                )
            else:
                builder.add(
                    "Reporter",
                    "Rejection propagated downstream",
                    "No Rollback or Retry route was selected.",
                    TimelineStatus.FAILED,
                )
        elif failure == "Infinite Loop":
            builder.add(
                "Coordinator",
                "Coordinator entered repeated route",
                "The repeated Analyzer route reached round 5.",
                TimelineStatus.RUNNING,
                round_number=5,
            )
            if guarded:
                builder.add(
                    "System",
                    "Infinite Loop Guardrail triggered",
                    "round_number reached max_rounds.",
                    TimelineStatus.GUARDRAIL_TRIGGERED,
                )
                builder.add(
                    "Coordinator",
                    "Forced route to Reporter",
                    "The repeated route was stopped.",
                    TimelineStatus.FORCED_ROUTE,
                )
            else:
                builder.add(
                    "Coordinator",
                    "Still Running",
                    (
                        "The integrated timeline preview paused at its display "
                        "limit; the repeated route was not terminated."
                    ),
                    TimelineStatus.STILL_RUNNING,
                    demo_display_limit_reached=True,
                )
        elif failure == "Privacy Leak":
            builder.add(
                "Reporter",
                "Sensitive final trace detected",
                "Safe placeholders: [EMAIL REDACTED], [API TOKEN REDACTED].",
                TimelineStatus.RUNNING,
            )
            if guarded:
                builder.add(
                    "Trace System",
                    "Privacy Guardrail sanitized final trace",
                    "Two fields were redacted before persistence.",
                    TimelineStatus.GUARDRAIL_TRIGGERED,
                    privacy_redaction_count=2,
                )
            else:
                builder.add(
                    "Trace System",
                    "Sensitive fields would be exposed",
                    "No real secret is shown in this demonstration.",
                    TimelineStatus.FAILED,
                )

    all_contained = all(mitigated[failure] for failure in failures)
    if all_contained:
        builder.add(
            "Reporter",
            "Safe Exit",
            "All injected failures were contained in one integrated execution.",
            TimelineStatus.SAFE_EXIT,
        )
    else:
        builder.add(
            "System",
            "Integrated execution failed",
            "One or more injected failures remained uncontained.",
            TimelineStatus.FAILED,
        )


def _scenario_metrics(
    scenario: str,
    failures: tuple[str, ...],
    mitigated: dict[str, bool],
    duration: float,
) -> dict[str, object]:
    selected = failures if scenario == "Multiple Failures" else (scenario,)
    metrics: dict[str, object] = {"Execution duration": f"{duration:.2f}s"}
    if "Infinite Loop" in selected:
        safe = mitigated.get("Infinite Loop", True)
        metrics.update(
            {
                "Rounds executed": 5,
                "Estimated tokens": 4600 if safe else 7800,
                "Safe exit": "Yes" if safe else "No",
            }
        )
    if "Structured Output Failure" in selected:
        safe = mitigated.get("Structured Output Failure", True)
        metrics.update(
            {
                "Schema failures": 1,
                "Correction retries": 1 if safe else 0,
                "Invalid payloads forwarded": 0 if safe else 1,
            }
        )
    if "Rogue Tool Call" in selected:
        safe = mitigated.get("Rogue Tool Call", True)
        metrics.update(
            {
                "Unauthorized requests": 1,
                "Unauthorized executions": 0 if safe else 1,
                "Blocked executions": 1 if safe else 0,
            }
        )
    if "Cascade Failure" in selected:
        safe = mitigated.get("Cascade Failure", True)
        metrics.update(
            {
                "Validation failures": 1,
                "Rollback count": 1 if safe else 0,
                "Retry count": 1 if safe else 0,
                "Final success": "Yes" if safe else "No",
            }
        )
    if "Privacy Leak" in selected:
        safe = mitigated.get("Privacy Leak", True)
        metrics.update(
            {
                "Sensitive fields detected": 2,
                "Sensitive fields exposed": 0 if safe else 2,
                "Fields redacted": 2 if safe else 0,
            }
        )
    if "Context Explosion" in selected:
        safe = mitigated.get("Context Explosion", True)
        metrics.update(
            {
                "Peak context size": "14,500 tokens",
                "Final context size": "5,200 tokens" if safe else "14,500 tokens",
                "Estimated token reduction": "9,300" if safe else "0",
            }
        )
    if scenario == "Happy Path":
        metrics.update(
            {
                "Rounds executed": 1,
                "Validation failures": 0,
                "Final success": "Yes",
            }
        )
    return metrics


def run_demo(
    prompt: str,
    selected_failures: Iterable[str],
    *,
    scenario: str | None = None,
    execution_mode: str = "WITH Guardrail",
    selected_guardrails: Iterable[str] | None = None,
) -> DemoResult:
    """Create one timeline while calling the existing live loop/tool adapters.

    The optional keyword arguments drive the redesigned UI. The original two-argument
    call remains supported for existing tests and callers.
    """
    failures = _normalize_failures(selected_failures)
    legacy_call = scenario is None and selected_guardrails is None
    if scenario is None:
        scenario = (
            "Happy Path"
            if not failures
            else failures[0]
            if len(failures) == 1
            else "Multiple Failures"
        )
    if selected_guardrails is None:
        active_guardrails = (
            tuple(GUARDRAILS)
            if legacy_call and not failures
            else tuple(SCENARIO_GUARDRAIL[failure] for failure in failures)
        )
    else:
        active_guardrails = tuple(
            guardrail
            for guardrail in dict.fromkeys(selected_guardrails)
            if guardrail in GUARDRAILS
        )

    with_guardrails = execution_mode == "WITH Guardrail"
    mitigated = {
        failure: (
            with_guardrails
            and SCENARIO_GUARDRAIL[failure] in active_guardrails
        )
        for failure in failures
    }
    loop_check = run_live_loop_check(
        inject_failure="Infinite Loop" in failures
        and mitigated.get("Infinite Loop", False)
    )
    tool_check = run_live_tool_check(
        inject_failure="Rogue Tool Call" in failures
        and mitigated.get("Rogue Tool Call", False)
    )

    builder = _TimelineBuilder()
    if scenario == "Happy Path":
        _render_happy_path(builder)
    elif scenario == "Multiple Failures":
        _render_multiple(
            builder,
            failures,
            mitigated,
            tool_message=tool_check.message,
        )
    elif scenario == "Infinite Loop":
        _render_loop(
            builder,
            mitigated=mitigated["Infinite Loop"],
            live_rounds=loop_check.rounds if loop_check.triggered else 5,
        )
    elif scenario == "Structured Output Failure":
        _render_structured(
            builder,
            mitigated=mitigated["Structured Output Failure"],
        )
    elif scenario == "Rogue Tool Call":
        _render_rogue(
            builder,
            mitigated=mitigated["Rogue Tool Call"],
            message=tool_check.message,
        )
    elif scenario == "Cascade Failure":
        _render_cascade(builder, mitigated=mitigated["Cascade Failure"])
    elif scenario == "Privacy Leak":
        _render_privacy(builder, mitigated=mitigated["Privacy Leak"])
    elif scenario == "Context Explosion":
        _render_context(builder, mitigated=mitigated["Context Explosion"])
    else:
        raise ValueError(f"Unsupported scenario: {scenario}")

    triggered_guardrails = tuple(
        SCENARIO_GUARDRAIL[failure]
        for failure in failures
        if mitigated[failure]
    )
    all_contained = not failures or all(mitigated.values())
    if scenario == "Infinite Loop" and not all_contained:
        final_status = "Still Running — maximum demo events reached"
    elif all_contained:
        final_status = "Safe Exit" if failures else "Completed"
    else:
        final_status = "Failed — uncontained failure"

    retry_count = int(
        mitigated.get("Structured Output Failure", False)
    ) + int(mitigated.get("Cascade Failure", False))
    rollback_count = int(mitigated.get("Cascade Failure", False))
    current_round = (
        5
        if "Infinite Loop" in failures
        else 1
    )
    duration = round(0.54 + len(builder.events) * 0.07, 2)

    summary = ExecutionSummary(
        scenario=scenario,
        execution_mode=execution_mode,
        selected_guardrails=active_guardrails,
        current_round=current_round,
        retry_count=retry_count,
        rollback_count=rollback_count,
        triggered_guardrails=triggered_guardrails,
        final_status=final_status,
        duration_seconds=duration,
    )

    node_statuses = {node: NodeStatus.SUCCESS for node in PIPELINE_NODES}
    node_guardrails: dict[str, list[str]] = {node: [] for node in PIPELINE_NODES}
    for failure in failures:
        node = _AFFECTED_NODE[failure]
        node_statuses[node] = (
            NodeStatus.GUARDED if mitigated[failure] else NodeStatus.FAILED
        )
        if mitigated[failure]:
            node_guardrails[node].append(SCENARIO_GUARDRAIL[failure])

    guardrails: list[GuardrailView] = []
    for failure, (icon, title, description, implementation) in GUARDRAIL_COPY.items():
        chosen = title in active_guardrails
        triggered = failure in failures and mitigated.get(failure, False)
        if legacy_call and not failures:
            status = GuardrailStatus.ENABLED
            trigger_reason = "No failure was injected."
            action = "The guardrail remained enabled without intervening."
        elif triggered:
            status = GuardrailStatus.TRIGGERED
            trigger_reason = _TRIGGER_REASONS[failure]
            action = _RESULTING_ACTIONS[failure]
        elif not chosen or not with_guardrails:
            status = GuardrailStatus.DISABLED
            trigger_reason = (
                "Execution Mode is WITHOUT Guardrail."
                if chosen and not with_guardrails
                else "Not selected for this demonstration."
            )
            action = "No guardrail action was taken."
        else:
            status = GuardrailStatus.NOT_TRIGGERED
            trigger_reason = "No matching failure reached this guardrail."
            action = "The guardrail observed the run without intervening."
        guardrails.append(
            GuardrailView(
                key=failure,
                icon=icon,
                title=title,
                description=description,
                status=status,
                implementation=(
                    "Live"
                    if implementation == "Live backend"
                    else "Mock Demonstration"
                    if implementation == "Mock UI state"
                    else implementation
                ),
                trigger_reason=trigger_reason,
                resulting_action=action,
            )
        )

    failure_summary = (
        "No failure was injected; the nominal route completed."
        if not failures
        else "All injected failures were contained before unsafe execution."
        if all_contained
        else "One or more injected failures remained uncontained in this mode."
    )
    final_output = (
        "The system completed safely with the selected mitigation."
        if all_contained and failures
        else "The system completed the task through the nominal route."
        if not failures
        else "The demonstration ended in an unsafe or incomplete state."
    )
    loop_degraded = mitigated.get("Infinite Loop", False)
    final_validation = all_contained and not loop_degraded

    agent_state = {
        "raw_input": prompt,
        "round_number": current_round,
        "max_rounds": 5,
        "analysis_retry_count": int(
            mitigated.get("Structured Output Failure", False)
        ),
        "analysis_schema_error": (
            "Structured Output Failure" in failures
            and not mitigated.get("Structured Output Failure", False)
        ),
        "is_validated": final_validation,
        "rejection_flag": (
            "Cascade Failure" in failures
            and not mitigated.get("Cascade Failure", False)
        ),
        "rollback_requested": False,
        "validation_result": {
            "accepted": final_validation,
            "rollback_required": (
                "Cascade Failure" in failures
                and not mitigated.get("Cascade Failure", False)
            ),
        },
        "next_route": (
            "worker_d_reporter"
            if all_contained
            else "worker_a_analyzer"
            if scenario == "Infinite Loop"
            else None
        ),
        "termination_reason": (
            "round_limit_reached"
            if scenario == "Infinite Loop" and mitigated.get("Infinite Loop", False)
            else "completed"
            if all_contained
            else None
        ),
        "degraded_output": loop_degraded,
        "privacy_redaction_count": 2 if mitigated.get("Privacy Leak", False) else 0,
        "context_metrics": {
            "before_tokens": 14500 if "Context Explosion" in failures else 0,
            "after_tokens": (
                5200
                if mitigated.get("Context Explosion", False)
                else 14500
                if "Context Explosion" in failures
                else 0
            ),
        },
        "final_report": final_output,
    }

    metrics = _scenario_metrics(scenario, failures, mitigated, duration)
    timeline = tuple(
        replace(event, status=TimelineStatus.COMPLETED)
        if event.status is TimelineStatus.RUNNING
        else event
        for event in builder.events
    )
    return DemoResult(
        prompt=prompt,
        node_statuses=node_statuses,
        node_guardrails={
            node: tuple(labels) for node, labels in node_guardrails.items()
        },
        timeline=timeline,
        guardrails=tuple(guardrails),
        agent_state=agent_state,
        execution_status=final_status,
        execution_time_seconds=duration,
        triggered_guardrails=triggered_guardrails,
        failure_summary=failure_summary,
        final_output=final_output,
        scenario=scenario,
        execution_mode=execution_mode,
        selected_guardrails=active_guardrails,
        summary=summary,
        metrics=metrics,
        live_checks={
            "loop_guard": {
                "live": True,
                "triggered": loop_check.triggered,
                "rounds": loop_check.rounds,
                "reason": loop_check.reason,
            },
            "tool_guard": {
                "live": True,
                "triggered": tool_check.triggered,
                "approved": tool_check.approved_count,
                "executed": tool_check.executed_count,
                "message": tool_check.message,
            },
        },
    )
