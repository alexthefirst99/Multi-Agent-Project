"""Side-effect-free tool handlers for the assignment domain."""

from __future__ import annotations

from collections.abc import Mapping

from contract import (
    CancelOrderRequest,
    ComplianceAlertRequest,
    ExecuteTradeRequest,
    ToolRequest,
)
from orchestrator.tools.registry import RegisteredTool, ToolRegistry


def mock_execute_trade(request: ToolRequest) -> Mapping[str, object]:
    if not isinstance(request, ExecuteTradeRequest):
        raise TypeError("mock_execute_trade requires ExecuteTradeRequest.")
    args = request.arguments
    return {
        "tool_name": request.tool_name,
        "success": True,
        "status": "mock_success",
        "reference_id": f"MOCK-TRADE-{args.ticker}-{args.quantity}",
        "ticker": args.ticker,
        "side": args.side,
        "quantity": args.quantity,
    }


def mock_cancel_order(request: ToolRequest) -> Mapping[str, object]:
    if not isinstance(request, CancelOrderRequest):
        raise TypeError("mock_cancel_order requires CancelOrderRequest.")
    return {
        "tool_name": request.tool_name,
        "success": True,
        "status": "mock_cancelled",
        "reference_id": f"MOCK-CANCEL-{request.arguments.order_id}",
        "message": "Mock order cancellation accepted.",
    }


def mock_send_compliance_alert(request: ToolRequest) -> Mapping[str, object]:
    if not isinstance(request, ComplianceAlertRequest):
        raise TypeError("mock_send_compliance_alert requires ComplianceAlertRequest.")
    return {
        "tool_name": request.tool_name,
        "success": True,
        "status": "mock_alerted",
        "reference_id": "MOCK-COMPLIANCE-ALERT",
        "message": request.arguments.message,
    }


def build_default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            RegisteredTool("execute_trade", mock_execute_trade),
            RegisteredTool("cancel_order", mock_cancel_order),
            RegisteredTool("send_compliance_alert", mock_send_compliance_alert),
        ]
    )
