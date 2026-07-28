"""Atomic tool-call validation and mock execution middleware."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from pydantic import JsonValue, TypeAdapter, ValidationError

from contract import ToolRequest
from orchestrator.tools.registry import ToolPermission, ToolRegistry

_TOOL_REQUEST_ADAPTER = TypeAdapter(ToolRequest)


class InvalidToolCallException(ValueError):
    """Raised when any requested call violates name, schema, permission, or bounds."""

    def __init__(self, index: int, reason: str) -> None:
        super().__init__(f"Tool call at index {index} was rejected: {reason}")
        self.index = index
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ToolBatchResult:
    approved_calls: tuple[ToolRequest, ...]
    raw_results: tuple[Mapping[str, object], ...]


def _permission_map(
    registry: ToolRegistry,
    permissions: Sequence[ToolPermission] | None,
) -> dict[str, bool]:
    if permissions is None:
        return {name: True for name in registry.names}
    resolved = {permission.name: permission.allowed for permission in permissions}
    unknown = set(resolved) - registry.names
    if unknown:
        raise ValueError(f"Permissions reference unregistered tools: {sorted(unknown)}")
    return {name: resolved.get(name, False) for name in registry.names}


def validate_tool_batch(
    raw_calls: Sequence[JsonValue],
    registry: ToolRegistry,
    *,
    permissions: Sequence[ToolPermission] | None = None,
) -> tuple[ToolRequest, ...]:
    """Validate the complete batch before any handler is invoked."""
    allowed = _permission_map(registry, permissions)
    validated: list[ToolRequest] = []
    for index, raw_call in enumerate(raw_calls):
        try:
            request = _TOOL_REQUEST_ADAPTER.validate_python(raw_call)
        except ValidationError as exc:
            raise InvalidToolCallException(index, str(exc)) from exc
        if request.tool_name not in registry.names:
            raise InvalidToolCallException(index, "tool name is not registered")
        if not allowed.get(request.tool_name, False):
            raise InvalidToolCallException(index, "runtime permission denied")
        validated.append(request)
    return tuple(validated)


def guard_and_execute_tool_batch(
    raw_calls: Sequence[JsonValue],
    registry: ToolRegistry,
    *,
    permissions: Sequence[ToolPermission] | None = None,
) -> ToolBatchResult:
    approved = validate_tool_batch(raw_calls, registry, permissions=permissions)
    results = tuple(registry.get(call.tool_name).handler(call) for call in approved)
    return ToolBatchResult(approved_calls=approved, raw_results=results)
