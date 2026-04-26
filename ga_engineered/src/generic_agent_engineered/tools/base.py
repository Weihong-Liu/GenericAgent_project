"""Provider-neutral tool definitions."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

EMPTY_PARAMETERS: dict[str, Any] = {"type": "object", "properties": {}}
TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")

ToolReturn = str | dict[str, Any] | ToolResult | Awaitable[Any]
ToolHandler = Callable[[ToolCall], ToolReturn]


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: dict(EMPTY_PARAMETERS))

    def __post_init__(self) -> None:
        validate_tool_name(self.name)
        if not isinstance(self.description, str):
            raise TypeError("tool description must be a string")
        if not isinstance(self.parameters, dict):
            raise TypeError("tool parameters must be a dict")
        object.__setattr__(self, "parameters", dict(self.parameters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class ToolPermission:
    name: str
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("tool permission name is required")
        if not isinstance(self.reason, str):
            raise TypeError("tool permission reason must be a string")


@dataclass(frozen=True)
class ToolSpec:
    schema: ToolSchema
    permissions: tuple[ToolPermission, ...] = ()
    enabled_by_default: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.schema, ToolSchema):
            raise TypeError("tool spec schema must be a ToolSchema")
        object.__setattr__(self, "permissions", tuple(self.permissions))
        if not isinstance(self.enabled_by_default, bool):
            raise TypeError("enabled_by_default must be a bool")

    @property
    def name(self) -> str:
        return self.schema.name

    def schema_dict(self) -> dict[str, Any]:
        return self.schema.to_dict()


@runtime_checkable
class Tool(Protocol):
    @property
    def spec(self) -> ToolSpec:
        """Static schema and permission metadata."""

    async def run(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call and return a normalized result."""


@dataclass
class FunctionTool:
    spec: ToolSpec
    handler: ToolHandler

    async def run(self, tool_call: ToolCall) -> ToolResult:
        raw_result = self.handler(tool_call)
        if inspect.isawaitable(raw_result):
            raw_result = await raw_result
        return coerce_tool_result(tool_call, raw_result)


def validate_tool_name(name: str) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("tool name is required")
    if not TOOL_NAME_PATTERN.match(name):
        raise ValueError(
            "tool name must start with a letter or underscore and contain only "
            "letters, numbers, underscores, or hyphens"
        )


def coerce_tool_result(tool_call: ToolCall, raw_result: Any) -> ToolResult:
    if isinstance(raw_result, ToolResult):
        if raw_result.tool_use_id != tool_call.id:
            raise ValueError("tool result id does not match tool call id")
        return raw_result

    if isinstance(raw_result, dict):
        metadata = raw_result.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        content = raw_result.get("content", raw_result)
        return ToolResult(
            tool_use_id=tool_call.id,
            content=_stringify_content(content),
            is_error=bool(raw_result.get("is_error", False)),
            metadata=metadata,
        )

    return ToolResult(tool_use_id=tool_call.id, content=_stringify_content(raw_result))


def tool_error_result(tool_call: ToolCall, message: str) -> ToolResult:
    return ToolResult(tool_use_id=tool_call.id, content=message, is_error=True)


def _stringify_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
