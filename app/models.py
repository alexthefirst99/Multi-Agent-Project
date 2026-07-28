"""Typed presentation models used by the Streamlit control center."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class NodeStatus(StrEnum):
    WAITING = "Waiting"
    RUNNING = "Running"
    SUCCESS = "Success"
    FAILED = "Failed"
    GUARDED = "Guardrail Triggered"


class GuardrailStatus(StrEnum):
    ENABLED = "Enabled"
    TRIGGERED = "Triggered"
    NOT_TRIGGERED = "Not Triggered"
    DISABLED = "Disabled"


class TimelineStatus(StrEnum):
    RUNNING = "Running"
    STILL_RUNNING = "Still Running"
    STOPPED = "Stopped"
    COMPLETED = "Completed"
    REJECTED = "Rejected"
    ROLLED_BACK = "Rolled Back"
    GUARDRAIL_TRIGGERED = "Guardrail Triggered"
    FORCED_ROUTE = "Forced Route"
    FAILED = "Failed"
    SAFE_EXIT = "Safe Exit"


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    sequence: int
    timestamp: str
    source: str
    title: str
    detail: str
    status: TimelineStatus
    state_changes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuardrailView:
    key: str
    icon: str
    title: str
    description: str
    status: GuardrailStatus
    implementation: str
    trigger_reason: str
    resulting_action: str


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    scenario: str
    execution_mode: str
    selected_guardrails: tuple[str, ...]
    current_round: int
    retry_count: int
    rollback_count: int
    triggered_guardrails: tuple[str, ...]
    final_status: str
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class DemoResult:
    prompt: str
    node_statuses: dict[str, NodeStatus]
    node_guardrails: dict[str, tuple[str, ...]]
    timeline: tuple[TimelineEvent, ...]
    guardrails: tuple[GuardrailView, ...]
    agent_state: dict[str, Any]
    execution_status: str
    execution_time_seconds: float
    triggered_guardrails: tuple[str, ...]
    failure_summary: str
    final_output: str
    scenario: str
    execution_mode: str
    selected_guardrails: tuple[str, ...]
    summary: ExecutionSummary
    metrics: dict[str, object]
    live_checks: dict[str, Any] = field(default_factory=dict)
