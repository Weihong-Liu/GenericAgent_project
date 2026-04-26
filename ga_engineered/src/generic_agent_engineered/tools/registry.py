"""Tool registry and execution gateway."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

from .base import Tool, tool_error_result, validate_tool_name


class ToolRegistryError(RuntimeError):
    """Base tool registry error."""


class DuplicateToolError(ToolRegistryError, ValueError):
    """Raised when a tool name is registered twice."""


class UnknownToolError(ToolRegistryError, KeyError):
    """Raised when resolving an unknown tool."""


class DisabledToolError(ToolRegistryError):
    """Raised when a disabled tool is requested in strict paths."""


@dataclass(frozen=True)
class RegisteredTool:
    tool: Tool
    enabled: bool

    @property
    def name(self) -> str:
        return self.tool.spec.name


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        self._enabled: dict[str, bool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool, *, enabled: bool | None = None) -> None:
        name = tool.spec.name
        validate_tool_name(name)
        if name in self._tools:
            raise DuplicateToolError(f"duplicate tool: {name}")
        self._tools[name] = tool
        self._enabled[name] = tool.spec.enabled_by_default if enabled is None else enabled

    def resolve(self, name: str, *, include_disabled: bool = False) -> Tool:
        normalized = _normalize_name(name)
        tool = self._tools.get(normalized)
        if tool is None:
            raise UnknownToolError(f"unknown tool: {normalized}")
        if not include_disabled and not self._enabled[normalized]:
            raise DisabledToolError(f"tool is disabled: {normalized}")
        return tool

    def enable(self, name: str) -> None:
        normalized = _normalize_name(name)
        self._require_known(normalized)
        self._enabled[normalized] = True

    def disable(self, name: str) -> None:
        normalized = _normalize_name(name)
        self._require_known(normalized)
        self._enabled[normalized] = False

    def is_enabled(self, name: str) -> bool:
        normalized = _normalize_name(name)
        self._require_known(normalized)
        return self._enabled[normalized]

    def list_tools(self, *, include_disabled: bool = True) -> tuple[RegisteredTool, ...]:
        registrations = (
            RegisteredTool(tool, self._enabled[name]) for name, tool in self._tools.items()
        )
        if include_disabled:
            return tuple(registrations)
        return tuple(registration for registration in registrations if registration.enabled)

    def schemas(self, *, include_disabled: bool = False) -> list[dict[str, object]]:
        return [
            registration.tool.spec.schema_dict()
            for registration in self.list_tools(include_disabled=include_disabled)
        ]

    async def run(self, tool_call: ToolCall) -> ToolResult:
        tool = self._tools.get(tool_call.name)
        if tool is None:
            return tool_error_result(tool_call, f"unknown tool: {tool_call.name}")
        if not self._enabled[tool_call.name]:
            return tool_error_result(tool_call, f"tool is disabled: {tool_call.name}")

        try:
            return await tool.run(tool_call)
        except Exception as exc:
            return tool_error_result(tool_call, f"tool failed: {exc}")

    def _require_known(self, name: str) -> None:
        if name not in self._tools:
            raise UnknownToolError(f"unknown tool: {name}")


def _normalize_name(name: str) -> str:
    normalized = name.strip()
    validate_tool_name(normalized)
    return normalized
