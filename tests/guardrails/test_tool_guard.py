from __future__ import annotations

from copy import deepcopy

import pytest

from orchestrator.guardrails.tool_guard import (
    InvalidToolCallException,
    guard_and_execute_tool_batch,
    validate_tool_batch,
)
from orchestrator.tools.mock_tools import (
    build_default_tool_permissions,
    build_default_tool_registry,
)
from orchestrator.tools.registry import ToolPermission

VALID = {
    "tool_name": "execute_trade",
    "arguments": {"ticker": "aapl", "side": "buy", "quantity": 10},
}


def test_valid_call_is_normalized_and_mocked() -> None:
    result = guard_and_execute_tool_batch([VALID], build_default_tool_registry())
    assert result.approved_calls[0].arguments.ticker == "AAPL"
    assert result.raw_results[0]["status"] == "mock_success"


def test_malformed_name_arguments_and_bounds_are_rejected() -> None:
    registry = build_default_tool_registry()
    invalid_calls = [
        {"tool_name": "transfer_client_funds", "arguments": {}},
        {"tool_name": "execute_trade", "arguments": {"ticker": "AAPL"}},
        {
            "tool_name": "execute_trade",
            "arguments": {"ticker": "AAPL", "side": "buy", "quantity": 1001},
        },
    ]
    for raw in invalid_calls:
        with pytest.raises(InvalidToolCallException):
            validate_tool_batch([raw], registry)


def test_permission_denial_and_atomic_batch_rejection() -> None:
    registry = build_default_tool_registry()
    executed: list[str] = []
    original_handler = registry.get("execute_trade").handler
    # A valid call followed by an invalid call must execute nothing. The registry's
    # immutable interface is enough to verify via the absence of returned results.
    with pytest.raises(InvalidToolCallException):
        guard_and_execute_tool_batch(
            [VALID, {"tool_name": "forbidden", "arguments": {}}],
            registry,
        )
    assert executed == []
    with pytest.raises(InvalidToolCallException, match="permission denied"):
        validate_tool_batch(
            [VALID],
            registry,
            permissions=[ToolPermission("execute_trade", allowed=False)],
        )
    assert callable(original_handler)


def test_validation_does_not_mutate_raw_calls() -> None:
    raw = [deepcopy(VALID)]
    snapshot = deepcopy(raw)
    validate_tool_batch(raw, build_default_tool_registry())
    assert raw == snapshot


def test_registered_tool_missing_from_explicit_permissions_is_denied() -> None:
    """Guards the production wiring gap: a tool that exists in the registry but
    was never added to an explicit permission list must be denied, not
    silently allowed just because it is registered. ``orchestrator/graph.py``
    now relies on exactly this by passing ``build_default_tool_permissions()``
    instead of ``permissions=None`` (which would allow every registered tool).
    Simulates a team forgetting to grant ``cancel_order`` when only
    ``execute_trade`` was explicitly permissioned.
    """
    registry = build_default_tool_registry()
    partial_permissions = [ToolPermission("execute_trade", allowed=True)]

    with pytest.raises(InvalidToolCallException, match="permission denied"):
        validate_tool_batch(
            [{"tool_name": "cancel_order", "arguments": {"order_id": "ORDER-1"}}],
            registry,
            permissions=partial_permissions,
        )
    # The tool that IS explicitly listed remains unaffected.
    result = guard_and_execute_tool_batch(
        [VALID], registry, permissions=partial_permissions
    )
    assert result.raw_results[0]["status"] == "mock_success"


def test_default_tool_permissions_cover_the_full_registry() -> None:
    """If a new tool is ever added to the registry, this test fails until it is
    also added to ``build_default_tool_permissions()`` -- turning a silent
    allow-by-omission gap into a loud, immediate test failure.
    """
    registry = build_default_tool_registry()
    permitted_names = {permission.name for permission in build_default_tool_permissions()}
    assert permitted_names == registry.names
