"""Canonical frozen Pydantic contract shared by every graph component.

Contract version: 2.0.0
Freeze status: FROZEN
Domain: Financial Trading Bot

The intentionally untrusted boundary fields are ``pending_tool_calls`` and
``pending_actor_output``. Guardrails must parse those JSON-compatible values
before promoting them into the typed, authoritative fields.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
    field_validator,
)

CONTRACT_VERSION = "2.0.0"
CONTRACT_FROZEN = True
MAX_COORDINATOR_ROUNDS = 5

NodeName = Literal[
    "context_manager",
    "coordinator",
    "worker_a_analyzer",
    "worker_b_actor",
    "worker_c_validator",
    "worker_d_reporter",
]
RouteName = Literal[
    "worker_a_analyzer",
    "worker_b_actor",
    "worker_d_reporter",
]
TerminationReason = Literal[
    "completed",
    "round_limit_reached",
    "analysis_schema_error",
    "tool_guard_rejection",
    "cascade_rejection",
]
MessageRole = Literal["system", "user", "assistant", "tool"]
MessageKind = Literal[
    "system_instruction",
    "conversation",
    "tool_output",
    "summary",
]
TradeSide = Literal["buy", "sell"]
RiskLevel = Literal["low", "medium", "high"]
ErrorCode = Literal[
    "analysis_schema_error",
    "unauthorized_tool_call",
    "malformed_actor_output",
    "business_validation_error",
    "round_limit_reached",
    "tracing_error",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, strict=True)


class MessageRecord(StrictModel):
    role: MessageRole
    content: str = Field(min_length=1)
    kind: MessageKind = "conversation"
    name: str | None = None
    essential: bool = False
    obsolete: bool = False

    @model_validator(mode="before")
    @classmethod
    def preserve_system_messages(cls, value: object) -> object:
        if isinstance(value, dict):
            data = dict(value)
            if data.get("role") == "system" or data.get("kind") == "system_instruction":
                data["essential"] = True
                data["kind"] = "system_instruction"
            return data
        return value


class AnalysisPayload(StrictModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z0-9.\-]+$")
    side: TradeSide
    quantity: int = Field(gt=0, le=1_000)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=10, max_length=1_000)
    risk_level: RiskLevel

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class ExecuteTradeArguments(StrictModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z0-9.\-]+$")
    side: TradeSide
    quantity: int = Field(gt=0, le=1_000)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class CancelOrderArguments(StrictModel):
    order_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class ComplianceAlertArguments(StrictModel):
    severity: Literal["low", "medium", "high", "critical"]
    message: str = Field(min_length=5, max_length=1_000)


class ExecuteTradeRequest(StrictModel):
    tool_name: Literal["execute_trade"]
    arguments: ExecuteTradeArguments


class CancelOrderRequest(StrictModel):
    tool_name: Literal["cancel_order"]
    arguments: CancelOrderArguments


class ComplianceAlertRequest(StrictModel):
    tool_name: Literal["send_compliance_alert"]
    arguments: ComplianceAlertArguments


ToolRequest = Annotated[
    Union[ExecuteTradeRequest, CancelOrderRequest, ComplianceAlertRequest],
    Field(discriminator="tool_name"),
]


class ToolExecutionResult(StrictModel):
    tool_name: Literal["execute_trade", "cancel_order", "send_compliance_alert"]
    success: bool
    status: Literal["mock_success", "mock_cancelled", "mock_alerted", "mock_failed"]
    reference_id: str = Field(min_length=3, max_length=100)
    ticker: str | None = Field(default=None, max_length=10)
    side: TradeSide | None = None
    quantity: int | None = Field(default=None, gt=0, le=1_000)
    message: str | None = Field(default=None, max_length=1_000)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_optional_ticker(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class ValidationResult(StrictModel):
    accepted: bool
    rollback_required: bool = False
    reason: str
    checked_items: int = Field(default=0, ge=0)


class GraphError(StrictModel):
    code: ErrorCode
    message: str = Field(min_length=1)
    node: NodeName
    recoverable: bool


class RouteAuditEntry(StrictModel):
    round_number: int = Field(ge=1)
    next_route: RouteName
    reason: str
    degraded: bool


class ContextMetrics(StrictModel):
    before_tokens: int = Field(default=0, ge=0)
    after_tokens: int = Field(default=0, ge=0)
    pruned_messages: int = Field(default=0, ge=0)
    summarized_messages: int = Field(default=0, ge=0)


class AgentState(StrictModel):
    """Universal graph state. No node may redefine this schema."""

    task_domain: Literal["financial_trading_bot"] = "financial_trading_bot"
    raw_input: str = Field(min_length=1)

    # Coordinator and deterministic loop guard.
    round_number: int = Field(default=0, ge=0)
    max_rounds: Literal[5] = MAX_COORDINATOR_ROUNDS
    next_route: RouteName | None = None
    route_reason: str | None = None
    routing_history: list[RouteAuditEntry] = Field(default_factory=list)
    degraded_output: bool = False
    termination_reason: TerminationReason | None = None

    # Structured analyzer output.
    analysis_payload: AnalysisPayload | None = None
    analysis_retry_count: int = Field(default=0, ge=0, le=1)
    analysis_schema_error: bool = False

    # Tool boundary, approved requests, and actor boundary.
    pending_tool_calls: list[JsonValue] = Field(default_factory=list)
    approved_tool_calls: list[ToolRequest] = Field(default_factory=list)
    pending_actor_output: list[JsonValue] = Field(default_factory=list)
    tool_execution_results: list[ToolExecutionResult] = Field(default_factory=list)

    # Validator state and rollback routing.
    validation_result: ValidationResult | None = None
    rejection_flag: bool = False
    rejection_reason: str | None = None
    rollback_requested: bool = False
    is_validated: bool = False

    # Context and privacy metadata.
    messages: list[MessageRecord] = Field(default_factory=list)
    context_summary: str | None = None
    context_metrics: ContextMetrics = Field(default_factory=ContextMetrics)
    privacy_redaction_count: int = Field(default=0, ge=0)

    # Explicit errors and final reporting.
    errors: list[GraphError] = Field(default_factory=list)
    final_report: str | None = None
