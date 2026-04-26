"""Provider-neutral runtime message models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

MessageRole = Literal["system", "user", "assistant", "tool"]
VALID_ROLES = frozenset({"system", "user", "assistant", "tool"})


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("tool call id is required")
        if not self.name:
            raise ValueError("tool call name is required")
        if not isinstance(self.arguments, dict):
            raise TypeError("tool call arguments must be a dict")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ToolCall:
        return cls(
            id=_required_str(values, "id"),
            name=_required_str(values, "name"),
            arguments=_dict_or_empty(values.get("arguments")),
        )


@dataclass(frozen=True)
class ToolResult:
    tool_use_id: str
    content: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tool_use_id:
            raise ValueError("tool_result tool_use_id is required")
        if not isinstance(self.content, str):
            raise TypeError("tool_result content must be a string")
        if not isinstance(self.metadata, dict):
            raise TypeError("tool_result metadata must be a dict")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_use_id": self.tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ToolResult:
        return cls(
            tool_use_id=_required_str(values, "tool_use_id"),
            content=_required_str(values, "content"),
            is_error=bool(values.get("is_error", False)),
            metadata=_dict_or_empty(values.get("metadata")),
        )


@dataclass(frozen=True)
class Message:
    role: MessageRole
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_result: ToolResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in VALID_ROLES:
            raise ValueError(f"invalid message role: {self.role}")
        if not isinstance(self.content, str):
            raise TypeError("message content must be a string")
        if not isinstance(self.metadata, dict):
            raise TypeError("message metadata must be a dict")

        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        if self.role == "tool" and self.tool_result is None:
            raise ValueError("tool messages require a tool_result")
        if self.role != "tool" and self.tool_result is not None:
            raise ValueError("tool_result is only valid on tool messages")
        if self.role != "assistant" and self.tool_calls:
            raise ValueError("tool_calls are only valid on assistant messages")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_calls:
            payload["tool_calls"] = [tool_call.to_dict() for tool_call in self.tool_calls]
        if self.tool_result is not None:
            payload["tool_result"] = self.tool_result.to_dict()
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Message:
        role = _required_str(values, "role")
        return cls(
            role=_coerce_role(role),
            content=str(values.get("content", "")),
            tool_calls=_tool_calls(values.get("tool_calls")),
            tool_result=_tool_result(values.get("tool_result")),
            metadata=_dict_or_empty(values.get("metadata")),
        )

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls,
        content: str = "",
        *,
        tool_calls: list[ToolCall] | tuple[ToolCall, ...] = (),
    ) -> Message:
        return cls(role="assistant", content=content, tool_calls=tuple(tool_calls))

    @classmethod
    def tool(cls, result: ToolResult) -> Message:
        return cls(role="tool", content=result.content, tool_result=result)


ChatMessage = Message


@dataclass(frozen=True)
class ChatResponse:
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("chat response content must be a string")
        if not isinstance(self.metadata, dict):
            raise TypeError("chat response metadata must be a dict")
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))

    def to_message(self) -> Message:
        return Message.assistant(self.content, tool_calls=self.tool_calls)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"content": self.content}
        if self.tool_calls:
            payload["tool_calls"] = [tool_call.to_dict() for tool_call in self.tool_calls]
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ChatResponse:
        return cls(
            content=str(values.get("content", "")),
            tool_calls=_tool_calls(values.get("tool_calls")),
            metadata=_dict_or_empty(values.get("metadata")),
        )


def serialize_messages(messages: list[Message] | tuple[Message, ...]) -> list[dict[str, Any]]:
    return [message.to_dict() for message in messages]


def deserialize_messages(values: list[dict[str, Any]]) -> list[Message]:
    return [Message.from_dict(item) for item in values]


def pair_tool_results(
    assistant_message: Message,
    tool_messages: list[Message] | tuple[Message, ...],
) -> dict[str, ToolResult]:
    if assistant_message.role != "assistant":
        raise ValueError("tool result pairing requires an assistant message")
    expected_ids = {tool_call.id for tool_call in assistant_message.tool_calls}
    results: dict[str, ToolResult] = {}
    for message in tool_messages:
        if message.role != "tool" or message.tool_result is None:
            raise ValueError("tool result pairing only accepts tool messages")
        if message.tool_result.tool_use_id not in expected_ids:
            raise ValueError(f"unmatched tool result: {message.tool_result.tool_use_id}")
        if message.tool_result.tool_use_id in results:
            raise ValueError(f"duplicate tool result: {message.tool_result.tool_use_id}")
        results[message.tool_result.tool_use_id] = message.tool_result
    missing = expected_ids - set(results)
    if missing:
        raise ValueError(f"missing tool results: {', '.join(sorted(missing))}")
    return results


def _required_str(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _dict_or_empty(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    raise TypeError("expected a dict")


def _coerce_role(role: str) -> MessageRole:
    if role not in VALID_ROLES:
        raise ValueError(f"invalid message role: {role}")
    return cast(MessageRole, role)


def _tool_calls(value: Any) -> tuple[ToolCall, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise TypeError("tool_calls must be a list")
    if not all(isinstance(item, dict) for item in value):
        raise TypeError("tool_calls entries must be objects")
    return tuple(ToolCall.from_dict(item) for item in value)


def _tool_result(value: Any) -> ToolResult | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("tool_result must be an object")
    return ToolResult.from_dict(value)
