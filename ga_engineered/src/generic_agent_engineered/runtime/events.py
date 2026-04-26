"""Runtime event models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

from .messages import ChatResponse, Message, ToolCall, ToolResult

RuntimeEventKind = Literal[
    "turn_started",
    "content_delta",
    "tool_call",
    "tool_result",
    "message_done",
    "turn_finished",
    "loop_stopped",
    "error",
]


@dataclass(frozen=True)
class RuntimeEvent:
    kind: RuntimeEventKind
    delta: str = ""
    message: Message | None = None
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    response: ChatResponse | None = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"invalid runtime event kind: {self.kind}")
        if not isinstance(self.delta, str):
            raise TypeError("runtime event delta must be a string")
        if not isinstance(self.error, str):
            raise TypeError("runtime event error must be a string")
        if not isinstance(self.metadata, dict):
            raise TypeError("runtime event metadata must be a dict")
        self._validate_shape()

    @classmethod
    def content_delta(cls, delta: str, *, metadata: dict[str, Any] | None = None) -> RuntimeEvent:
        return cls(kind="content_delta", delta=delta, metadata=metadata or {})

    @classmethod
    def turn_started(cls, turn: int) -> RuntimeEvent:
        return cls(kind="turn_started", metadata={"turn": turn})

    @classmethod
    def turn_finished(cls, turn: int, *, reason: str) -> RuntimeEvent:
        return cls(kind="turn_finished", metadata={"turn": turn, "reason": reason})

    @classmethod
    def loop_stopped(cls, *, reason: str, turn: int | None = None) -> RuntimeEvent:
        metadata: dict[str, Any] = {"reason": reason}
        if turn is not None:
            metadata["turn"] = turn
        return cls(kind="loop_stopped", metadata=metadata)

    @classmethod
    def from_tool_call(
        cls,
        tool_call: ToolCall,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        return cls(kind="tool_call", tool_call=tool_call, metadata=metadata or {})

    @classmethod
    def from_tool_result(
        cls,
        tool_result: ToolResult,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        return cls(kind="tool_result", tool_result=tool_result, metadata=metadata or {})

    @classmethod
    def message_done(
        cls,
        response: ChatResponse,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        return cls(kind="message_done", response=response, metadata=metadata or {})

    @classmethod
    def failure(cls, error: str, *, metadata: dict[str, Any] | None = None) -> RuntimeEvent:
        return cls(kind="error", error=error, metadata=metadata or {})

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind}
        if self.delta:
            payload["delta"] = self.delta
        if self.message is not None:
            payload["message"] = self.message.to_dict()
        if self.tool_call is not None:
            payload["tool_call"] = self.tool_call.to_dict()
        if self.tool_result is not None:
            payload["tool_result"] = self.tool_result.to_dict()
        if self.response is not None:
            payload["response"] = self.response.to_dict()
        if self.error:
            payload["error"] = self.error
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> RuntimeEvent:
        kind = _coerce_kind(values.get("kind"))
        return cls(
            kind=kind,
            delta=str(values.get("delta", "")),
            message=_message(values.get("message")),
            tool_call=_tool_call(values.get("tool_call")),
            tool_result=_tool_result(values.get("tool_result")),
            response=_response(values.get("response")),
            error=str(values.get("error", "")),
            metadata=_dict_or_empty(values.get("metadata")),
        )

    def _validate_shape(self) -> None:
        if self.kind == "content_delta" and not self.delta:
            raise ValueError("content_delta events require delta")
        if self.kind == "tool_call" and self.tool_call is None:
            raise ValueError("tool_call events require tool_call")
        if self.kind == "tool_result" and self.tool_result is None:
            raise ValueError("tool_result events require tool_result")
        if self.kind == "message_done" and self.response is None:
            raise ValueError("message_done events require response")
        if self.kind == "error" and not self.error:
            raise ValueError("error events require error text")


StreamEvent = RuntimeEvent


_VALID_KINDS = frozenset(
    {
        "content_delta",
        "turn_started",
        "tool_call",
        "tool_result",
        "message_done",
        "turn_finished",
        "loop_stopped",
        "error",
    }
)


def _coerce_kind(value: Any) -> RuntimeEventKind:
    if value not in _VALID_KINDS:
        raise ValueError(f"invalid runtime event kind: {value}")
    return cast(RuntimeEventKind, value)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    raise TypeError("expected a dict")


def _message(value: Any) -> Message | None:
    return Message.from_dict(value) if isinstance(value, dict) else None


def _tool_call(value: Any) -> ToolCall | None:
    return ToolCall.from_dict(value) if isinstance(value, dict) else None


def _tool_result(value: Any) -> ToolResult | None:
    return ToolResult.from_dict(value) if isinstance(value, dict) else None


def _response(value: Any) -> ChatResponse | None:
    return ChatResponse.from_dict(value) if isinstance(value, dict) else None
