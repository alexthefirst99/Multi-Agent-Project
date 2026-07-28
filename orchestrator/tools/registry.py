"""Typed registry for approved mock tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from contract import ToolRequest

MockToolHandler = Callable[[ToolRequest], Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class ToolPermission:
    name: str
    allowed: bool = True


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    name: str
    handler: MockToolHandler


class ToolRegistry:
    """Immutable-by-convention registry with explicit lookup failures."""

    def __init__(self, tools: list[RegisteredTool]) -> None:
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("Tool names must be unique.")
        self._tools = {tool.name: tool for tool in tools}

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._tools)

    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool {name!r} is not registered.") from exc
